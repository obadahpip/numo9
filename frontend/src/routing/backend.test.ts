import { backendRewrites } from "./backend";

describe("backendRewrites", () => {
  it("is empty without a backend URL", () => {
    expect(backendRewrites(undefined)).toEqual([]);
    expect(backendRewrites("  ")).toEqual([]);
  });

  it("forwards the API and the authentication paths only", () => {
    expect(backendRewrites("http://backend:8000/")).toEqual([
      { source: "/api/v1/:path*", destination: "http://backend:8000/api/v1/:path*" },
      { source: "/_allauth/:path*", destination: "http://backend:8000/_allauth/:path*" },
    ]);
  });

  it("refuses a relative or non-http URL", () => {
    expect(() => backendRewrites("backend:8000")).toThrow(/http/);
    expect(() => backendRewrites("ftp://backend")).toThrow(/http or https/);
  });
});
