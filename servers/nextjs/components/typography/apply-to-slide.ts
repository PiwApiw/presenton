import type {
  TypographyConfig,
  TypographyRoleConfig,
  TypographyRoleName,
} from "./effective";

type FontLike = {
  family?: string | null;
  size?: number | null;
  manual?: boolean | null;
};

type SlideNode = {
  type?: string;
  name?: string;
  id?: string;
  font?: FontLike;
  runs?: Array<{ font?: FontLike }>;
  elements?: SlideNode[];
};

const EXCLUDED_ROLE_NAME = /(footer|page[_-]?number|badge|caption|label|kicker)/i;

function collectTextNodes(node: SlideNode, output: SlideNode[]): void {
  if (!node || typeof node !== "object") return;
  if (Array.isArray(node.elements)) {
    for (const child of node.elements) collectTextNodes(child, output);
  }
  if (
    typeof node.type === "string" &&
    node.type.includes("text") &&
    node.font != null
  ) {
    output.push(node);
  }
}

function applyRole(node: SlideNode, config: TypographyRoleConfig): void {
  const previousSize = node.font?.size ?? null;
  if (config.size != null) {
    node.font = { ...node.font, size: config.size };
  }
  if (config.family) {
    node.font = { ...node.font, family: config.family };
  }
  if (config.size != null && previousSize) {
    const ratio = config.size / previousSize;
    node.runs = node.runs?.map((run) =>
      run.font?.size
        ? { ...run, font: { ...run.font, size: Math.round(run.font.size * ratio) } }
        : run,
    );
  }
}

export function applyTypographyToSlide<T>(
  layout: T,
  config?: TypographyConfig | null,
): T {
  if (!config || !layout) return layout;

  const clone = structuredClone(layout) as unknown as SlideNode;
  const nodes: SlideNode[] = [];
  collectTextNodes(clone, nodes);

  const editable = nodes.filter((node) => node.font?.manual !== true);
  if (editable.length === 0) return clone as unknown as T;

  const candidates = editable.filter(
    (node) => !EXCLUDED_ROLE_NAME.test(`${node.name ?? ""} ${node.id ?? ""}`),
  );
  const ranked = [...candidates].sort(
    (a, b) => (b.font?.size ?? 0) - (a.font?.size ?? 0),
  );
  const title = ranked[0];
  const titleSize = title?.font?.size ?? 0;
  const subtitle = ranked.find(
    (node) =>
      node !== title &&
      titleSize > 0 &&
      (node.font?.size ?? 0) < titleSize &&
      (node.font?.size ?? 0) >= titleSize * 0.6,
  );

  const assignments = new Map<SlideNode, TypographyRoleName>();
  if (title) assignments.set(title, "title");
  if (subtitle) assignments.set(subtitle, "subtitle");
  for (const node of editable) {
    if (!assignments.has(node)) assignments.set(node, "body");
  }

  for (const [node, role] of assignments) {
    const roleConfig = config.roles?.[role];
    if (roleConfig) applyRole(node, roleConfig);
  }

  return clone as unknown as T;
}