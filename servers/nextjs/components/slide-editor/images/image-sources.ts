export type StockProviderId = "pexels" | "pixabay";
export type ImageSourceId = "stock" | "ai";

export type ImageSourceAvailability = {
  /** Provider to query for stock results, or null when stock is unavailable. */
  stockProvider: StockProviderId | null;
  /** Key from user settings; the backend falls back to its own environment key. */
  stockApiKey: string | null;
  stockAvailable: boolean;
  aiAvailable: boolean;
  aiProvider: string | null;
  aiBlockedReason: "disabled" | "stock-provider" | "no-provider" | null;
  /** Sources to offer, in display order. */
  availableSources: ImageSourceId[];
  defaultSource: ImageSourceId | null;
};

type LlmConfigLike =
  | {
      DISABLE_IMAGE_GENERATION?: boolean | null;
      IMAGE_PROVIDER?: string | null;
      PEXELS_API_KEY?: string | null;
      PIXABAY_API_KEY?: string | null;
    }
  | null
  | undefined;

const STOCK_PROVIDER_IDS: StockProviderId[] = ["pexels", "pixabay"];

export function normalizeImageProvider(value: string | null | undefined) {
  const provider = (value || "").trim().toLowerCase();
  if (provider === "pixels" || provider === "pixel" || provider === "pexel") {
    return "pexels";
  }
  return provider;
}

export function isStockProviderId(
  value: string | null | undefined,
): value is StockProviderId {
  const provider = normalizeImageProvider(value);
  return provider === "pexels" || provider === "pixabay";
}

function readKey(value: string | null | undefined) {
  return (value || "").trim() || null;
}

/**
 * Stock search and AI generation are independent backends: the stock endpoint
 * takes an explicit provider and only needs a key, while generation always uses
 * the configured IMAGE_PROVIDER. A stock IMAGE_PROVIDER therefore means "no AI".
 */
export function resolveImageSources(
  llmConfig: LlmConfigLike,
): ImageSourceAvailability {
  const provider = normalizeImageProvider(llmConfig?.IMAGE_PROVIDER);
  const generationDisabled = Boolean(llmConfig?.DISABLE_IMAGE_GENERATION);
  const keys: Record<StockProviderId, string | null> = {
    pexels: readKey(llmConfig?.PEXELS_API_KEY),
    pixabay: readKey(llmConfig?.PIXABAY_API_KEY),
  };

  const selectedStock = isStockProviderId(provider) ? provider : null;
  const stockProvider: StockProviderId | null =
    selectedStock ?? STOCK_PROVIDER_IDS.find((id) => keys[id]) ?? null;
  const stockAvailable = stockProvider !== null;
  const stockApiKey = stockProvider ? keys[stockProvider] : null;

  const aiProvider = provider && !selectedStock ? provider : null;
  const aiBlockedReason: ImageSourceAvailability["aiBlockedReason"] =
    generationDisabled
      ? "disabled"
      : selectedStock
        ? "stock-provider"
        : aiProvider
          ? null
          : "no-provider";
  const aiAvailable = aiBlockedReason === null;

  const availableSources: ImageSourceId[] = [];
  if (stockAvailable) availableSources.push("stock");
  if (aiAvailable) availableSources.push("ai");

  const defaultSource: ImageSourceId | null =
    selectedStock && stockAvailable
      ? "stock"
      : aiAvailable
        ? "ai"
        : stockAvailable
          ? "stock"
          : null;

  return {
    stockProvider,
    stockApiKey,
    stockAvailable,
    aiAvailable,
    aiProvider,
    aiBlockedReason,
    availableSources,
    defaultSource,
  };
}
