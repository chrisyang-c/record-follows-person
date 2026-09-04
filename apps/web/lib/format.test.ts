import { describe, expect, it } from "vitest";
import { fmtNum, fmtPct } from "./format";

describe("format", () => {
  it("formats percent and numbers without hardcoded separators", () => {
    expect(fmtPct(0.5)).toBe("50%");
    expect(fmtPct(null)).toBe("—");
    expect(fmtNum(3.14159)).toBe("3.1");
  });
});
