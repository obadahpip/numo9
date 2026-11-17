/** Console route guard (U-06-T02): `GET /api/v1/platform/me`. */
import { apiRequest, type ApiResult } from "@/auth/client";

export interface PlatformMe {
  id: string;
  name: string;
  email: string;
  permissions: string[];
}

export const getPlatformMe = (): Promise<ApiResult<PlatformMe>> =>
  apiRequest<PlatformMe>("/api/v1/platform/me");
