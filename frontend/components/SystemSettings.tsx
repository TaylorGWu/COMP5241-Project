"use client";

import { useState } from "react";

import { Segmented } from "@/components/ui";
import { LOCALES, LOCALE_LABELS, type Locale } from "@/lib/i18n-config";
import { useI18n } from "@/lib/i18n";
import { useTheme, type ThemePreference } from "@/lib/theme";

/** Global preferences belong to the product shell, never a particular course or chapter. */
export function SystemSettings() {
  const [open, setOpen] = useState(false);
  const { t, locale, setLocale } = useI18n();
  const { preference, setPreference } = useTheme();

  return (
    <div className="global-system-settings" data-global-system-settings="1">
      {open ? (
        <section id="global-system-settings" className="global-system-settings__panel" aria-label={t.settings.title}>
          <div className="global-system-settings__head">
            <div>
              <p>{t.settings.title}</p>
              <span>{t.settings.scope}</span>
            </div>
            <button type="button" onClick={() => setOpen(false)} aria-label={`Close ${t.settings.title}`}>×</button>
          </div>
          <div className="global-system-settings__section">
            <p>{t.settings.appearance}</p>
            <Segmented<ThemePreference>
              value={preference}
              onChange={setPreference}
              label={t.settings.appearance}
              options={[
                { value: "system", label: t.settings.system },
                { value: "light", label: t.settings.light },
                { value: "dark", label: t.settings.dark },
              ]}
            />
          </div>
          <div className="global-system-settings__section">
            <p>{t.settings.language}</p>
            <Segmented<Locale>
              value={locale}
              onChange={setLocale}
              label={t.settings.language}
              options={LOCALES.map((language) => ({
                value: language,
                label: LOCALE_LABELS[language].short,
                title: LOCALE_LABELS[language].native,
              }))}
            />
          </div>
        </section>
      ) : null}
      <button
        type="button"
        className="global-system-settings__trigger"
        aria-expanded={open}
        aria-controls="global-system-settings"
        onClick={() => setOpen((value) => !value)}
      >
        <span aria-hidden>◌</span>
        {t.settings.title}
      </button>
    </div>
  );
}
