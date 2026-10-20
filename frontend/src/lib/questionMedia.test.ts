import { describe, expect, it } from "vitest";
import { mediaTypeForUpload } from "./questionMedia";

describe("mediaTypeForUpload (Task 1)", () => {
  it("keeps image, audio and video uploads as their own media type", () => {
    expect(mediaTypeForUpload("image")).toBe("image");
    expect(mediaTypeForUpload("audio")).toBe("audio");
    expect(mediaTypeForUpload("video")).toBe("video");
  });

  it("falls back to the previous 'image' default for types question media does not allow", () => {
    expect(mediaTypeForUpload("document")).toBe("image");
    expect(mediaTypeForUpload("")).toBe("image");
  });
});
