import { useSyncExternalStore } from "react";

/** 頂欄只顯示「角色 + 住民姓名」；病人頁掛載時把名字放進來，離開時清掉。 */
let current = "";
const listeners = new Set<() => void>();
export function setPatientTitle(name: string) {
  current = name;
  listeners.forEach((l) => l());
}
export function usePatientTitle() {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    () => current,
    () => "",
  );
}
