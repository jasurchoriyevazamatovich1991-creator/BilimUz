import { describe, expect, it } from "vitest";
import { deriveDistinctValues } from "./deriveOptions";

interface Item {
  region: string | null;
}

describe("deriveDistinctValues", () => {
  it("returns sorted, deduplicated values", () => {
    const items: Item[] = [{ region: "Toshkent" }, { region: "Andijon" }, { region: "Toshkent" }];
    expect(deriveDistinctValues(items, "region")).toEqual(["Andijon", "Toshkent"]);
  });

  it("skips null and empty-string values", () => {
    const items: Item[] = [{ region: null }, { region: "" }, { region: "Farg'ona" }];
    expect(deriveDistinctValues(items, "region")).toEqual(["Farg'ona"]);
  });

  it("returns an empty array for an empty dataset", () => {
    expect(deriveDistinctValues([] as Item[], "region")).toEqual([]);
  });
});
