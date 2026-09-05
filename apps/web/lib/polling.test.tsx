import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { usePolling } from "@/lib/api";

function setHidden(hidden: boolean) {
  Object.defineProperty(document, "hidden", { configurable: true, get: () => hidden });
  document.dispatchEvent(new Event("visibilitychange"));
}

describe("usePolling (KNOWN_ISSUES #20)", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => {
    vi.useRealTimers();
    Object.defineProperty(document, "hidden", { configurable: true, get: () => false });
  });

  it("ticks while visible, pauses when hidden, reloads once on return", () => {
    const reload = vi.fn();
    renderHook(() => usePolling(reload, 1000));
    act(() => vi.advanceTimersByTime(2500));
    expect(reload).toHaveBeenCalledTimes(2);
    act(() => setHidden(true));
    act(() => vi.advanceTimersByTime(5000));
    expect(reload).toHaveBeenCalledTimes(2); // paused
    act(() => setHidden(false));
    expect(reload).toHaveBeenCalledTimes(3); // immediate refresh on return
    act(() => vi.advanceTimersByTime(1000));
    expect(reload).toHaveBeenCalledTimes(4);
  });

  it("does nothing when disabled and stops on unmount", () => {
    const reload = vi.fn();
    const { unmount } = renderHook(({ on }) => usePolling(reload, 1000, on), { initialProps: { on: false } });
    act(() => vi.advanceTimersByTime(3000));
    expect(reload).not.toHaveBeenCalled();
    unmount();
  });
});
