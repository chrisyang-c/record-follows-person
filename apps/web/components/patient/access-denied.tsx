import { Lock } from "lucide-react";

/** 不在 Care Circle 授權範圍：顯示「未獲授權」，不是 404。 */
export function AccessDenied({ what }: { what: string }) {
  return (
    <section role="alert" className="rounded-[12px] border border-line bg-surface p-6 text-center">
      <Lock className="mx-auto mb-2 size-6 text-ink-2" aria-hidden="true" />
      <p className="text-lg font-medium">未獲授權</p>
      <p className="mt-1 text-sm text-ink-2">你目前的身份沒有被授權看{what}。授權由本人或家屬在 Care Circle 設定。</p>
    </section>
  );
}
