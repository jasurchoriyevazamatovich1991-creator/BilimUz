import { afterEach, describe, expect, it } from "vitest";
import { readCsrfCookie } from "./csrfCookie";

function setDocumentCookie(value: string) {
  document.cookie = value;
}

function clearAllCookies() {
  // jsdom doesn't expose a bulk-clear API — expire everything this test
  // file might have set, by name, between tests.
  document.cookie = "csrf_token=; expires=Thu, 01 Jan 1970 00:00:00 GMT";
  document.cookie = "other_cookie=; expires=Thu, 01 Jan 1970 00:00:00 GMT";
}

describe("readCsrfCookie", () => {
  afterEach(clearAllCookies);

  it("returns null when no csrf_token cookie is present", () => {
    expect(readCsrfCookie()).toBeNull();
  });

  it("reads the csrf_token cookie's value", () => {
    setDocumentCookie("csrf_token=abc123");
    expect(readCsrfCookie()).toBe("abc123");
  });

  it("finds csrf_token among several other cookies", () => {
    setDocumentCookie("other_cookie=irrelevant");
    setDocumentCookie("csrf_token=the-real-value");
    expect(readCsrfCookie()).toBe("the-real-value");
  });

  it("URL-decodes the cookie value", () => {
    setDocumentCookie(`csrf_token=${encodeURIComponent("a+b/c=")}`);
    expect(readCsrfCookie()).toBe("a+b/c=");
  });

  it("never reads a refresh_token cookie value — no such capability exists", () => {
    // Documents the actual security property: even if a refresh_token
    // cookie were somehow readable (it shouldn't be — it's HttpOnly, so
    // this line wouldn't even see it in a real browser), this helper has
    // no code path that would ever return it; it only ever looks for
    // "csrf_token".
    setDocumentCookie("refresh_token=should-never-be-read-by-this-function");
    expect(readCsrfCookie()).toBeNull();
  });
});
