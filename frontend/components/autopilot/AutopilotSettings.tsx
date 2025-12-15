'use client'

/**
 * Autopilot Settings Component
 * SPEC-045 / TASK-048
 * 
 * Settings panel for configuring Autopilot behavior.
 */

import React from 'react'
import { Card } from '@/components/ui/card'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { Settings, Zap, Bell, Clock, X } from 'lucide-react'
import type { AutopilotSettings as AutopilotSettingsType, NotificationStyle } from '@/types/autopilot'
import { useAutopilot } from './AutopilotProvider'

export function AutopilotSettings() {
  const { settings, updateSettings, isLoading } = useAutopilot()
  
  if (isLoading || !settings) {
    return (
      <Card className="p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-gray-200 rounded w-1/3" />
          <div className="h-10 bg-gray-200 rounded" />
          <div className="h-10 bg-gray-200 rounded" />
        </div>
      </Card>
    )
  }
  
  const handleToggle = async (key: keyof AutopilotSettingsType, value: boolean) => {
    await updateSettings({ [key]: value })
  }
  
  const handleNotificationStyle = async (value: NotificationStyle) => {
    await updateSettings({ notification_style: value })
  }
  
  const handleNumberChange = async (key: keyof AutopilotSettingsType, value: number) => {
    await updateSettings({ [key]: value })
  }
  
  const removeKeyword = async (keyword: string) => {
    const newKeywords = settings.excluded_meeting_keywords.filter(k => k !== keyword)
    await updateSettings({ excluded_meeting_keywords: newKeywords })
  }
  
  const addKeyword = async (keyword: string) => {
    if (!keyword.trim()) return
    const newKeywords = [...settings.excluded_meeting_keywords, keyword.trim().toLowerCase()]
    await updateSettings({ excluded_meeting_keywords: newKeywords })
  }
  
  return (
    <Card className="p-6">
      <div className="flex items-center gap-2 mb-6">
        <Settings className="w-5 h-5 text-gray-500" />
        <h2 className="text-lg font-semibold text-gray-900">Autopilot Instellingen</h2>
      </div>
      
      <div className="space-y-6">
        {/* Master Toggle */}
        <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
          <div className="flex items-center gap-3">
            <Zap className="w-5 h-5 text-yellow-500" />
            <div>
              <Label htmlFor="enabled" className="text-base font-medium">
                Autopilot ingeschakeld
              </Label>
              <p className="text-sm text-gray-500">
                Luna detecteert automatisch kansen en maakt voorstellen
              </p>
            </div>
          </div>
          <Switch
            id="enabled"
            checked={settings.enabled}
            onCheckedChange={(checked) => handleToggle('enabled', checked)}
          />
        </div>
        
        {settings.enabled && (
          <>
            {/* Detection Settings */}
            <div>
              <h3 className="text-sm font-medium text-gray-700 mb-3">Detectie</h3>
              <div className="space-y-3">
                <SettingRow
                  id="auto_research_new_meetings"
                  label="Research voor nieuwe meetings"
                  description="Detecteer nieuwe bedrijven in je agenda"
                  checked={settings.auto_research_new_meetings}
                  onChange={(checked) => handleToggle('auto_research_new_meetings', checked)}
                />
                
                <SettingRow
                  id="auto_prep_known_prospects"
                  label="Prep voor bekende prospects"
                  description="Suggereer preps voor meetings zonder voorbereiding"
                  checked={settings.auto_prep_known_prospects}
                  onChange={(checked) => handleToggle('auto_prep_known_prospects', checked)}
                />
                
                <SettingRow
                  id="auto_followup_after_meeting"
                  label="Follow-up na meetings"
                  description="Suggereer follow-ups na afgelopen meetings"
                  checked={settings.auto_followup_after_meeting}
                  onChange={(checked) => handleToggle('auto_followup_after_meeting', checked)}
                />
              </div>
            </div>
            
            {/* Timing Settings */}
            <div>
              <h3 className="text-sm font-medium text-gray-700 mb-3">Timing</h3>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <Label htmlFor="prep_hours">Uren voor meeting</Label>
                    <p className="text-sm text-gray-500">
                      Hoeveel uur van tevoren suggesties maken
                    </p>
                  </div>
                  <Select
                    value={String(settings.prep_hours_before_meeting)}
                    onValueChange={(v) => handleNumberChange('prep_hours_before_meeting', parseInt(v))}
                  >
                    <SelectTrigger className="w-24">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="12">12 uur</SelectItem>
                      <SelectItem value="24">24 uur</SelectItem>
                      <SelectItem value="48">48 uur</SelectItem>
                      <SelectItem value="72">72 uur</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                
                <div className="flex items-center justify-between">
                  <div>
                    <Label htmlFor="reactivation_days">Reactivatie na dagen</Label>
                    <p className="text-sm text-gray-500">
                      Na hoeveel dagen stille prospects suggereren
                    </p>
                  </div>
                  <Select
                    value={String(settings.reactivation_days_threshold)}
                    onValueChange={(v) => handleNumberChange('reactivation_days_threshold', parseInt(v))}
                  >
                    <SelectTrigger className="w-24">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="7">7 dagen</SelectItem>
                      <SelectItem value="14">14 dagen</SelectItem>
                      <SelectItem value="21">21 dagen</SelectItem>
                      <SelectItem value="30">30 dagen</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </div>
            
            {/* Notification Style */}
            <div>
              <h3 className="text-sm font-medium text-gray-700 mb-3 flex items-center gap-2">
                <Bell className="w-4 h-4" />
                Notificatie stijl
              </h3>
              <Select
                value={settings.notification_style}
                onValueChange={handleNotificationStyle}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="eager">
                    <span className="font-medium">Actief</span>
                    <span className="text-gray-500 ml-2">- Direct notificeren</span>
                  </SelectItem>
                  <SelectItem value="balanced">
                    <span className="font-medium">Gebalanceerd</span>
                    <span className="text-gray-500 ml-2">- Slimme timing</span>
                  </SelectItem>
                  <SelectItem value="minimal">
                    <span className="font-medium">Minimaal</span>
                    <span className="text-gray-500 ml-2">- Alleen urgente items</span>
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
            
            {/* Excluded Keywords */}
            <div>
              <h3 className="text-sm font-medium text-gray-700 mb-3">
                Uitgesloten meeting keywords
              </h3>
              <p className="text-sm text-gray-500 mb-3">
                Meetings met deze woorden in de titel worden genegeerd
              </p>
              
              <div className="flex flex-wrap gap-2 mb-3">
                {settings.excluded_meeting_keywords.map((keyword) => (
                  <Badge key={keyword} variant="secondary" className="flex items-center gap-1">
                    {keyword}
                    <button
                      onClick={() => removeKeyword(keyword)}
                      className="hover:text-red-500"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </Badge>
                ))}
                {settings.excluded_meeting_keywords.length === 0 && (
                  <span className="text-sm text-gray-400">Geen keywords ingesteld</span>
                )}
              </div>
              
              <form
                onSubmit={(e) => {
                  e.preventDefault()
                  const input = e.currentTarget.querySelector('input')
                  if (input) {
                    addKeyword(input.value)
                    input.value = ''
                  }
                }}
                className="flex gap-2"
              >
                <Input
                  placeholder="Bijv. intern, standup, 1:1"
                  className="flex-1"
                />
                <button
                  type="submit"
                  className="px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-md text-sm font-medium transition-colors"
                >
                  Toevoegen
                </button>
              </form>
            </div>
          </>
        )}
      </div>
    </Card>
  )
}


interface SettingRowProps {
  id: string
  label: string
  description: string
  checked: boolean
  onChange: (checked: boolean) => void
}

function SettingRow({ id, label, description, checked, onChange }: SettingRowProps) {
  return (
    <div className="flex items-center justify-between p-3 border border-gray-100 rounded-lg">
      <div>
        <Label htmlFor={id} className="font-medium">{label}</Label>
        <p className="text-sm text-gray-500">{description}</p>
      </div>
      <Switch id={id} checked={checked} onCheckedChange={onChange} />
    </div>
  )
}
