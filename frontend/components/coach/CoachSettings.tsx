'use client'

import { useState } from 'react'
import { useTranslations } from 'next-intl'
import { useCoach } from './CoachProvider'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet'
import { Settings, X } from 'lucide-react'

interface CoachSettingsProps {
  trigger?: React.ReactNode
  open?: boolean
  onOpenChange?: (open: boolean) => void
}

export function CoachSettings({ 
  trigger, 
  open: controlledOpen, 
  onOpenChange 
}: CoachSettingsProps) {
  const t = useTranslations('coach.settings')
  const { settings, updateSettings, isLoading } = useCoach()
  const [internalOpen, setInternalOpen] = useState(false)
  
  const open = controlledOpen ?? internalOpen
  const setOpen = onOpenChange ?? setInternalOpen
  
  const handleEnabledChange = async (enabled: boolean) => {
    await updateSettings({ is_enabled: enabled })
  }
  
  const handleInlineTipsChange = async (enabled: boolean) => {
    await updateSettings({ show_inline_tips: enabled })
  }
  
  const handleCompletionModalsChange = async (enabled: boolean) => {
    await updateSettings({ show_completion_modals: enabled })
  }
  
  const handleFrequencyChange = async (frequency: string) => {
    await updateSettings({ notification_frequency: frequency as 'minimal' | 'normal' | 'frequent' })
  }

  const defaultTrigger = (
    <Button variant="ghost" size="icon" className="h-8 w-8">
      <Settings className="h-4 w-4" />
      <span className="sr-only">{t('title')}</span>
    </Button>
  )

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        {trigger || defaultTrigger}
      </SheetTrigger>
      <SheetContent className="sm:max-w-md">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            <span className="text-xl">🤖</span>
            {t('title')}
          </SheetTitle>
          <SheetDescription>
            Customize how Luna assists you
          </SheetDescription>
        </SheetHeader>
        
        <div className="mt-6 space-y-6">
          {/* Enable/Disable Coach */}
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label htmlFor="coach-enabled" className="font-medium">
                {t('enabled')}
              </Label>
              <p className="text-sm text-muted-foreground">
                Show the AI coach widget
              </p>
            </div>
            <Switch
              id="coach-enabled"
              checked={settings?.is_enabled ?? true}
              onCheckedChange={handleEnabledChange}
              disabled={isLoading}
            />
          </div>
          
          <div className="border-t pt-6">
            {/* Inline Tips */}
            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <Label htmlFor="inline-tips" className="font-medium">
                  {t('inlineTips')}
                </Label>
                <p className="text-sm text-muted-foreground">
                  Contextual hints on forms
                </p>
              </div>
              <Switch
                id="inline-tips"
                checked={settings?.show_inline_tips ?? true}
                onCheckedChange={handleInlineTipsChange}
                disabled={isLoading || !settings?.is_enabled}
              />
            </div>
            
            {/* Completion Modals */}
            <div className="flex items-center justify-between mt-4">
              <div className="space-y-0.5">
                <Label htmlFor="completion-modals" className="font-medium">
                  {t('completionModals')}
                </Label>
                <p className="text-sm text-muted-foreground">
                  Next step suggestions after tasks
                </p>
              </div>
              <Switch
                id="completion-modals"
                checked={settings?.show_completion_modals ?? true}
                onCheckedChange={handleCompletionModalsChange}
                disabled={isLoading || !settings?.is_enabled}
              />
            </div>
          </div>
          
          <div className="border-t pt-6">
            {/* Notification Frequency */}
            <div className="space-y-2">
              <Label htmlFor="frequency" className="font-medium">
                {t('frequency')}
              </Label>
              <Select
                value={settings?.notification_frequency ?? 'normal'}
                onValueChange={handleFrequencyChange}
                disabled={isLoading || !settings?.is_enabled}
              >
                <SelectTrigger id="frequency" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="minimal">
                    {t('frequencyOptions.minimal')}
                    <span className="text-xs text-muted-foreground ml-2">
                      – Only critical suggestions
                    </span>
                  </SelectItem>
                  <SelectItem value="normal">
                    {t('frequencyOptions.normal')}
                    <span className="text-xs text-muted-foreground ml-2">
                      – Balanced recommendations
                    </span>
                  </SelectItem>
                  <SelectItem value="frequent">
                    {t('frequencyOptions.frequent')}
                    <span className="text-xs text-muted-foreground ml-2">
                      – All helpful tips
                    </span>
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          
          {/* Info Section */}
          <div className="border-t pt-6">
            <div className="rounded-lg bg-muted/50 p-4">
              <h4 className="text-sm font-medium mb-2 flex items-center gap-2">
                <span>💡</span>
                How Luna learns
              </h4>
              <p className="text-sm text-muted-foreground">
                Luna learns from your workflow patterns to provide better suggestions. 
                The more you use the app, the smarter Luna becomes at helping you at the right time.
              </p>
            </div>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  )
}

