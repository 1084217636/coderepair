import { describe, expect, it } from "@rstest/core";

import { CODE_CHANGE_TEST_PROFILES } from "@/core/code-change/profiles";

describe("CODE_CHANGE_TEST_PROFILES", () => {
  it("uses the exact server-owned profile identifiers", () => {
    expect(CODE_CHANGE_TEST_PROFILES.map((profile) => profile.value)).toEqual([
      "python-pytest",
      "go-test",
      "frontend-check",
    ]);
  });
});
