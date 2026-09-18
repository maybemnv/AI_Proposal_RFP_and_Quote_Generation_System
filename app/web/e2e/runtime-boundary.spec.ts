import { expect, test } from "@playwright/test";

import { isLocalApiUrl } from "../lib/api";

test("production API boundary recognizes loopback URL forms", () => {
  expect(isLocalApiUrl("http://127.0.0.2:8106")).toBe(true);
  expect(isLocalApiUrl("http://[::1]:8106")).toBe(true);
  expect(isLocalApiUrl("https://api.example.com")).toBe(false);
});
