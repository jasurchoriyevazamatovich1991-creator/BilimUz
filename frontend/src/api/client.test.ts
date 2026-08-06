import { describe, expect, it } from "vitest";
import { ApiError, unwrap, type ApiEnvelope } from "./client";

describe("unwrap", () => {
  it("returns the data field from a successful envelope", async () => {
    const envelope: ApiEnvelope<{ id: string }> = {
      success: true,
      message: "OK",
      data: { id: "abc" },
      errors: null,
    };
    const result = await unwrap(Promise.resolve({ data: envelope }));
    expect(result).toEqual({ id: "abc" });
  });

  it("passes through primitive data types unchanged", async () => {
    const envelope: ApiEnvelope<null> = { success: true, message: "OK", data: null, errors: null };
    const result = await unwrap(Promise.resolve({ data: envelope }));
    expect(result).toBeNull();
  });
});

describe("ApiError", () => {
  it("carries message, field errors, and HTTP status", () => {
    const error = new ApiError("Xatolik", { phone: ["Noto'g'ri format"] }, 422);
    expect(error.message).toBe("Xatolik");
    expect(error.errors).toEqual({ phone: ["Noto'g'ri format"] });
    expect(error.status).toBe(422);
    expect(error.name).toBe("ApiError");
    expect(error).toBeInstanceOf(Error);
  });

  it("allows null errors and undefined status", () => {
    const error = new ApiError("Noma'lum xatolik", null, undefined);
    expect(error.errors).toBeNull();
    expect(error.status).toBeUndefined();
  });
});
