import { getApiUrl } from "@/utils/api";
import type { TypographyConfig } from "@/components/typography/effective";
import { getHeader } from "./header";

export type GoogleFontFace = { weight: number; style: string; url: string };
export type GoogleFontResponse = {
  family: string;
  url: string;
  faces: GoogleFontFace[];
};

export class TypographyService {
  static async resolveGoogleFont(
    family: string,
  ): Promise<GoogleFontResponse> {
    const response = await fetch(getApiUrl("/api/v1/ppt/fonts/google"), {
      method: "POST",
      headers: getHeader(),
      body: JSON.stringify({ family }),
      cache: "no-cache",
    });
    if (!response.ok) {
      const detail = await response.text();
      throw new Error(detail || "Gagal memuat Google Font");
    }
    return (await response.json()) as GoogleFontResponse;
  }

  static async updatePresentationTypography(
    presentationId: string,
    payload: {
      typography?: TypographyConfig | null;
      fonts?: Record<string, string>;
    },
  ): Promise<void> {
    const response = await fetch(
      getApiUrl(`/api/v1/ppt/presentation/${presentationId}/typography`),
      {
        method: "PATCH",
        headers: getHeader(),
        body: JSON.stringify(payload),
        cache: "no-cache",
      },
    );
    if (!response.ok) {
      const detail = await response.text();
      throw new Error(detail || "Gagal menyimpan tipografi");
    }
  }
}