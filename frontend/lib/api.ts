const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export type HealthStatus = { status: string; timestamp: string; service: string };

export async function getHealth(): Promise<HealthStatus> {
  const response = await fetch(`${API_URL}/health`);
  if (!response.ok) throw new Error("AlphaAgent API is unavailable");
  return response.json() as Promise<HealthStatus>;
}
