'use client'

import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { 
  Loader2, 
  Plus, 
  X, 
  RotateCcw, 
  Mic,
  Eye,
  Check,
  AlertCircle,
  Users,
  Clock
} from 'lucide-react'
import { useTranslations } from 'next-intl'
import { useToast } from '@/components/ui/use-toast'
import { api } from '@/lib/api'
import { logger } from '@/lib/logger'

interface AutoRecordSettings {
  id?: string
  enabled: boolean
  mode: 'all' | 'filtered' | 'none'
  external_only: boolean
  min_duration_minutes: number
  include_keywords: string[]
  exclude_keywords: string[]
  notify_before_join: boolean
  notify_minutes_before: number
}

interface PreviewMeeting {
  id: string
  title: string
  start_time: string
  is_online: boolean
  will_record: boolean
  reason: string
  matched_keyword?: string
}

interface PreviewResult {
  enabled: boolean
  total_meetings: number
  will_record: number
  will_skip: number
  meetings: PreviewMeeting[]
}

export function AutoRecordSettings() {
  const t = useTranslations('settings.autoRecord')
  const tCommon = useTranslations('common')
  const { toast } = useToast()

  const [settings, setSettings] = useState<AutoRecordSettings>({
    enabled: false,
    mode: 'filtered',
    external_only: true,
    min_duration_minutes: 15,
    include_keywords: [],
    exclude_keywords: [],
    notify_before_join: true,
    notify_minutes_before: 2
  })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [hasChanges, setHasChanges] = useState(false)
  const [originalSettings, setOriginalSettings] = useState<AutoRecordSettings | null>(null)
  
  // Keyword input states
  const [newIncludeKeyword, setNewIncludeKeyword] = useState('')
  const [newExcludeKeyword, setNewExcludeKeyword] = useState('')
  
  // Preview state
  const [previewLoading, setPreviewLoading] = useState(false)
  const [preview, setPreview] = useState<PreviewResult | null>(null)
  const [showPreview, setShowPreview] = useState(false)

  // Fetch settings on mount
  useEffect(() => {
    fetchSettings()
  }, [])

  // Track changes
  useEffect(() => {
    if (originalSettings) {
      const changed = JSON.stringify(settings) !== JSON.stringify(originalSettings)
      setHasChanges(changed)
    }
  }, [settings, originalSettings])

  const fetchSettings = async () => {
    setLoading(true)
    try {
      const { data, error } = await api.get<AutoRecordSettings>('/api/v1/auto-record/settings')
      if (error) throw new Error(typeof error === 'string' ? error : 'Failed to fetch settings')
      if (data) {
        setSettings(data)
        setOriginalSettings(data)
      }
    } catch (err) {
      logger.error('Failed to fetch auto-record settings', err)
      toast({
        title: t('error.fetchFailed'),
        variant: 'destructive'
      })
    } finally {
      setLoading(false)
    }
  }

  const saveSettings = async () => {
    setSaving(true)
    try {
      const { data, error } = await api.put<AutoRecordSettings>('/api/v1/auto-record/settings', settings)
      if (error) throw new Error(typeof error === 'string' ? error : 'Failed to save settings')
      if (data) {
        setSettings(data)
        setOriginalSettings(data)
        setHasChanges(false)
        toast({
          title: t('saved'),
          description: settings.enabled ? t('savedEnabled') : t('savedDisabled')
        })
      }
    } catch (error) {
      logger.error('Failed to save auto-record settings', error)
      toast({
        title: t('error.saveFailed'),
        variant: 'destructive'
      })
    } finally {
      setSaving(false)
    }
  }

  const resetKeywords = async () => {
    try {
      const { data, error } = await api.post<{ include_keywords: string[], exclude_keywords: string[] }>(
        '/api/v1/auto-record/settings/reset-keywords'
      )
      if (error) throw new Error(typeof error === 'string' ? error : 'Failed to reset keywords')
      if (data) {
        setSettings(prev => ({
          ...prev,
          include_keywords: data.include_keywords,
          exclude_keywords: data.exclude_keywords
        }))
        toast({
          title: t('keywordsReset'),
          description: t('keywordsResetDesc')
        })
      }
    } catch (error) {
      logger.error('Failed to reset keywords', error)
      toast({
        title: t('error.resetFailed'),
        variant: 'destructive'
      })
    }
  }

  const fetchPreview = async () => {
    setPreviewLoading(true)
    setShowPreview(true)
    try {
      const { data, error } = await api.get<PreviewResult>('/api/v1/auto-record/preview')
      if (error) throw new Error(typeof error === 'string' ? error : 'Failed to fetch preview')
      setPreview(data || null)
    } catch (err) {
      logger.error('Failed to fetch preview', err)
      toast({
        title: t('error.previewFailed'),
        variant: 'destructive'
      })
    } finally {
      setPreviewLoading(false)
    }
  }

  const addKeyword = (type: 'include' | 'exclude') => {
    const keyword = type === 'include' ? newIncludeKeyword.trim() : newExcludeKeyword.trim()
    if (!keyword) return

    const key = type === 'include' ? 'include_keywords' : 'exclude_keywords'
    if (settings[key].includes(keyword.toLowerCase())) {
      toast({
        title: t('keywordExists'),
        variant: 'destructive'
      })
      return
    }

    setSettings(prev => ({
      ...prev,
      [key]: [...prev[key], keyword.toLowerCase()]
    }))

    if (type === 'include') {
      setNewIncludeKeyword('')
    } else {
      setNewExcludeKeyword('')
    }
  }

  const removeKeyword = (type: 'include' | 'exclude', keyword: string) => {
    const key = type === 'include' ? 'include_keywords' : 'exclude_keywords'
    setSettings(prev => ({
      ...prev,
      [key]: prev[key].filter(k => k !== keyword)
    }))
  }

  const handleKeyDown = (e: React.KeyboardEvent, type: 'include' | 'exclude') => {
    if (e.key === 'Enter') {
      e.preventDefault()
      addKeyword(type)
    }
  }

  if (loading) {
    return (
      <Card>
        <CardContent className="py-8">
          <div className="flex items-center justify-center gap-2">
            <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
            <span className="text-sm text-slate-500">{tCommon('loading')}</span>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Mic className="h-5 w-5 text-orange-500" />
            <CardTitle>{t('title')}</CardTitle>
          </div>
          <Switch
            checked={settings.enabled}
            onCheckedChange={(enabled) => setSettings(prev => ({ ...prev, enabled }))}
          />
        </div>
        <CardDescription>
          {t('description')}
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-6">
        {/* Mode Selection */}
        <div className="space-y-3">
          <Label className="text-sm font-medium">{t('mode.label')}</Label>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
            {(['filtered', 'all', 'none'] as const).map((mode) => (
              <button
                key={mode}
                onClick={() => setSettings(prev => ({ ...prev, mode }))}
                disabled={!settings.enabled}
                className={`p-3 rounded-lg border text-left transition-all ${
                  settings.mode === mode
                    ? 'border-orange-500 bg-orange-50 dark:bg-orange-900/20'
                    : 'border-slate-200 dark:border-slate-700 hover:border-slate-300'
                } ${!settings.enabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
              >
                <p className="text-sm font-medium text-slate-900 dark:text-white">
                  {t(`mode.${mode}`)}
                </p>
                <p className="text-xs text-slate-500 mt-1">
                  {t(`mode.${mode}Desc`)}
                </p>
              </button>
            ))}
          </div>
        </div>

        {/* Filters - Only show when mode is 'filtered' */}
        {settings.mode === 'filtered' && settings.enabled && (
          <>
            {/* External Only Toggle */}
            <div className="flex items-center justify-between p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50">
              <div className="flex items-center gap-2">
                <Users className="h-4 w-4 text-slate-500" />
                <div>
                  <p className="text-sm font-medium text-slate-900 dark:text-white">
                    {t('externalOnly')}
                  </p>
                  <p className="text-xs text-slate-500">{t('externalOnlyDesc')}</p>
                </div>
              </div>
              <Switch
                checked={settings.external_only}
                onCheckedChange={(external_only) => setSettings(prev => ({ ...prev, external_only }))}
              />
            </div>

            {/* Minimum Duration */}
            <div className="flex items-center justify-between p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50">
              <div className="flex items-center gap-2">
                <Clock className="h-4 w-4 text-slate-500" />
                <div>
                  <p className="text-sm font-medium text-slate-900 dark:text-white">
                    {t('minDuration')}
                  </p>
                  <p className="text-xs text-slate-500">{t('minDurationDesc')}</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Input
                  type="number"
                  min={0}
                  max={480}
                  value={settings.min_duration_minutes}
                  onChange={(e) => setSettings(prev => ({ 
                    ...prev, 
                    min_duration_minutes: parseInt(e.target.value) || 0 
                  }))}
                  className="w-20 text-center"
                />
                <span className="text-sm text-slate-500">{t('minutes')}</span>
              </div>
            </div>

            {/* Include Keywords */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label className="text-sm font-medium text-green-700 dark:text-green-400">
                  ✓ {t('includeKeywords')}
                </Label>
                <Button variant="ghost" size="sm" onClick={resetKeywords} className="gap-1 text-xs">
                  <RotateCcw className="h-3 w-3" />
                  {t('resetDefaults')}
                </Button>
              </div>
              <p className="text-xs text-slate-500">{t('includeKeywordsDesc')}</p>
              <div className="flex flex-wrap gap-2">
                {settings.include_keywords.map((keyword) => (
                  <Badge 
                    key={keyword} 
                    variant="secondary" 
                    className="bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 gap-1"
                  >
                    {keyword}
                    <button onClick={() => removeKeyword('include', keyword)} className="hover:text-green-900">
                      <X className="h-3 w-3" />
                    </button>
                  </Badge>
                ))}
              </div>
              <div className="flex gap-2">
                <Input
                  placeholder={t('addKeywordPlaceholder')}
                  value={newIncludeKeyword}
                  onChange={(e) => setNewIncludeKeyword(e.target.value)}
                  onKeyDown={(e) => handleKeyDown(e, 'include')}
                  className="flex-1"
                />
                <Button 
                  variant="outline" 
                  size="sm" 
                  onClick={() => addKeyword('include')}
                  disabled={!newIncludeKeyword.trim()}
                >
                  <Plus className="h-4 w-4" />
                </Button>
              </div>
            </div>

            {/* Exclude Keywords */}
            <div className="space-y-3">
              <Label className="text-sm font-medium text-red-700 dark:text-red-400">
                ✗ {t('excludeKeywords')}
              </Label>
              <p className="text-xs text-slate-500">{t('excludeKeywordsDesc')}</p>
              <div className="flex flex-wrap gap-2">
                {settings.exclude_keywords.map((keyword) => (
                  <Badge 
                    key={keyword} 
                    variant="secondary" 
                    className="bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400 gap-1"
                  >
                    {keyword}
                    <button onClick={() => removeKeyword('exclude', keyword)} className="hover:text-red-900">
                      <X className="h-3 w-3" />
                    </button>
                  </Badge>
                ))}
              </div>
              <div className="flex gap-2">
                <Input
                  placeholder={t('addKeywordPlaceholder')}
                  value={newExcludeKeyword}
                  onChange={(e) => setNewExcludeKeyword(e.target.value)}
                  onKeyDown={(e) => handleKeyDown(e, 'exclude')}
                  className="flex-1"
                />
                <Button 
                  variant="outline" 
                  size="sm" 
                  onClick={() => addKeyword('exclude')}
                  disabled={!newExcludeKeyword.trim()}
                >
                  <Plus className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </>
        )}

        {/* Preview Button */}
        {settings.enabled && (
          <div className="pt-2">
            <Button 
              variant="outline" 
              onClick={fetchPreview}
              disabled={previewLoading}
              className="w-full gap-2"
            >
              {previewLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Eye className="h-4 w-4" />
              )}
              {t('preview')}
            </Button>
          </div>
        )}

        {/* Preview Results */}
        {showPreview && preview && (
          <div className="space-y-3 p-4 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700">
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-medium">{t('previewResults')}</h4>
              <button onClick={() => setShowPreview(false)}>
                <X className="h-4 w-4 text-slate-400 hover:text-slate-600" />
              </button>
            </div>
            
            <div className="flex gap-4 text-sm">
              <div className="flex items-center gap-1 text-green-600">
                <Check className="h-4 w-4" />
                <span>{t('willRecord', { count: preview.will_record })}</span>
              </div>
              <div className="flex items-center gap-1 text-slate-500">
                <AlertCircle className="h-4 w-4" />
                <span>{t('willSkip', { count: preview.will_skip })}</span>
              </div>
            </div>

            {preview.meetings.length > 0 && (
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {preview.meetings.slice(0, 10).map((meeting) => (
                  <div 
                    key={meeting.id}
                    className={`flex items-center justify-between p-2 rounded text-sm ${
                      meeting.will_record 
                        ? 'bg-green-100 dark:bg-green-900/20' 
                        : 'bg-slate-100 dark:bg-slate-700/50'
                    }`}
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      {meeting.will_record ? (
                        <Check className="h-3 w-3 text-green-600 flex-shrink-0" />
                      ) : (
                        <X className="h-3 w-3 text-slate-400 flex-shrink-0" />
                      )}
                      <span className="truncate">{meeting.title}</span>
                    </div>
                    <span className="text-xs text-slate-500 flex-shrink-0 ml-2">
                      {meeting.matched_keyword && (
                        <Badge variant="outline" className="text-xs">
                          {meeting.matched_keyword}
                        </Badge>
                      )}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Save Button */}
        {hasChanges && (
          <div className="flex justify-end pt-4 border-t">
            <Button onClick={saveSettings} disabled={saving} className="gap-2">
              {saving ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Check className="h-4 w-4" />
              )}
              {tCommon('save')}
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

