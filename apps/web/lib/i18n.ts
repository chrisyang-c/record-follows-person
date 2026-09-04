// Demo 語言只有 zh-TW；多語（id / vi）為第二階段（見 CLAUDE.md §12 註記）。
export type UiLang = "zh-TW";

export const T: Record<UiLang, Record<string, string>> = {
  "zh-TW": {
    title: "照護者回報",
    speak: "回去講一句",
    notes: "本月注意事項",
    resident: "住民",
    dontKnow: "不知道",
    sending: "傳送中…",
    errorRetry: "送不出去，請再試一次或直接告訴護理師。",
  },
};

export const SPEECH_LANG: Record<UiLang, string> = { "zh-TW": "zh-TW" };
