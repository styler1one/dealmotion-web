'use client';

import { useTranslations } from 'next-intl';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { 
  SUPPORTED_LANGUAGES, 
  LANGUAGE_INFO, 
  type SupportedLanguage 
} from '@/lib/language-utils';

interface LanguageSelectProps {
  value: string;
  onChange: (value: string) => void;
  label?: string;
  description?: string;
  showSuggestion?: boolean;
  suggestionSource?: string;
  disabled?: boolean;
  className?: string;
}

export function LanguageSelect({
  value,
  onChange,
  label,
  description,
  showSuggestion = false,
  suggestionSource,
  disabled = false,
  className = '',
}: LanguageSelectProps) {
  const t = useTranslations('language');

  return (
    <div className={`space-y-2 ${className}`}>
      {label && (
        <Label className="text-sm font-medium text-slate-700 dark:text-slate-300">
          {label}
        </Label>
      )}
      
      <Select value={value} onValueChange={onChange} disabled={disabled}>
        <SelectTrigger className="w-full bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700">
          <SelectValue placeholder="Select language">
            {value && (
              <span className="flex items-center gap-2">
                <span>{LANGUAGE_INFO[value as SupportedLanguage]?.flag}</span>
                <span>{t(`languages.${value}`)}</span>
              </span>
            )}
          </SelectValue>
        </SelectTrigger>
        <SelectContent className="bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700">
          {SUPPORTED_LANGUAGES.map((lang) => (
            <SelectItem 
              key={lang} 
              value={lang}
              className="hover:bg-slate-100 dark:hover:bg-slate-700"
            >
              <span className="flex items-center gap-2">
                <span>{LANGUAGE_INFO[lang].flag}</span>
                <span>{t(`languages.${lang}`)}</span>
              </span>
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {description && (
        <p className="text-xs text-slate-500 dark:text-slate-400">
          {description}
        </p>
      )}
      
      {showSuggestion && suggestionSource && (
        <p className="text-xs text-blue-600 dark:text-blue-400 flex items-center gap-1">
          <span>💡</span>
          <span>{t('suggestedFrom')}: {suggestionSource}</span>
        </p>
      )}
    </div>
  );
}

