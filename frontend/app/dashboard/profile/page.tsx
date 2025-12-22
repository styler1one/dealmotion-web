'use client'

import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { createClientComponentClient } from '@supabase/auth-helpers-nextjs'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { DashboardLayout } from '@/components/layout'
import { 
  User as UserIcon, 
  Briefcase, 
  Target, 
  Award,
  RefreshCw,
  Loader2,
  BookOpen,
  Wand2,
  Mail,
  Sparkles,
  Check,
  X,
  Pencil,
  Save,
  Plus,
  Trash2
} from 'lucide-react'
import { useTranslations } from 'next-intl'
import type { User } from '@supabase/supabase-js'

interface StyleGuide {
  tone?: string
  formality?: string
  language_style?: string
  persuasion_style?: string
  emoji_usage?: boolean
  signoff?: string
  writing_length?: string
  generated_at?: string
  confidence_score?: number
}

interface SalesProfileData {
  id: string
  full_name: string
  role: string | null
  experience_years: number | null
  sales_methodology: string | null
  methodology_description: string | null
  communication_style: string | null
  style_notes: string | null
  strengths: string[]
  areas_to_improve: string[]
  target_industries: string[]
  target_regions: string[]
  target_company_sizes: string[]
  quarterly_goals: string | null
  preferred_meeting_types: string[]
  ai_summary: string | null
  sales_narrative: string | null
  profile_completeness: number
  email_tone: string | null
  uses_emoji: boolean | null
  email_signoff: string | null
  writing_length_preference: string | null
  style_guide: StyleGuide | null
  created_at: string
  updated_at: string
}

// Editable Field Components
interface EditableTextProps {
  value: string | null
  field: string
  label: string
  onSave: (field: string, value: string) => Promise<void>
  placeholder?: string
  multiline?: boolean
}

function EditableText({ value, field, label, onSave, placeholder, multiline = false }: EditableTextProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [editValue, setEditValue] = useState(value || '')
  const [saving, setSaving] = useState(false)
  const t = useTranslations('profile')

  const handleSave = async () => {
    setSaving(true)
    try {
      await onSave(field, editValue)
      setIsEditing(false)
    } finally {
      setSaving(false)
    }
  }

  const handleCancel = () => {
    setEditValue(value || '')
    setIsEditing(false)
  }

  if (isEditing) {
    return (
      <div className="space-y-2">
        <p className="text-sm font-medium text-muted-foreground">{label}</p>
        {multiline ? (
          <Textarea
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            className="min-h-[100px]"
            placeholder={placeholder}
          />
        ) : (
          <Input
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            placeholder={placeholder}
          />
        )}
        <div className="flex gap-2">
          <Button size="sm" onClick={handleSave} disabled={saving}>
            {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : <Save className="h-3 w-3" />}
            <span className="ml-1">{t('save')}</span>
          </Button>
          <Button size="sm" variant="outline" onClick={handleCancel} disabled={saving}>
            <X className="h-3 w-3" />
            <span className="ml-1">{t('cancel')}</span>
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="group">
      <p className="text-sm font-medium text-muted-foreground">{label}</p>
      <div className="flex items-start justify-between gap-2">
        <p className="text-base text-gray-700 dark:text-slate-300">
          {value || <span className="text-muted-foreground italic">{t('notSet')}</span>}
        </p>
        <Button 
          size="sm" 
          variant="ghost" 
          className="opacity-0 group-hover:opacity-100 transition-opacity h-6 w-6 p-0"
          onClick={() => setIsEditing(true)}
        >
          <Pencil className="h-3 w-3" />
        </Button>
      </div>
    </div>
  )
}

interface EditableNumberProps {
  value: number | null
  field: string
  label: string
  suffix?: string
  onSave: (field: string, value: number | null) => Promise<void>
}

function EditableNumber({ value, field, label, suffix, onSave }: EditableNumberProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [editValue, setEditValue] = useState(value?.toString() || '')
  const [saving, setSaving] = useState(false)
  const t = useTranslations('profile')

  const handleSave = async () => {
    setSaving(true)
    try {
      const numValue = editValue ? parseInt(editValue, 10) : null
      await onSave(field, numValue)
      setIsEditing(false)
    } finally {
      setSaving(false)
    }
  }

  const handleCancel = () => {
    setEditValue(value?.toString() || '')
    setIsEditing(false)
  }

  if (isEditing) {
    return (
      <div className="space-y-2">
        <p className="text-sm font-medium text-muted-foreground">{label}</p>
        <Input
          type="number"
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          min="0"
        />
        <div className="flex gap-2">
          <Button size="sm" onClick={handleSave} disabled={saving}>
            {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : <Save className="h-3 w-3" />}
            <span className="ml-1">{t('save')}</span>
          </Button>
          <Button size="sm" variant="outline" onClick={handleCancel} disabled={saving}>
            <X className="h-3 w-3" />
            <span className="ml-1">{t('cancel')}</span>
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="group">
      <p className="text-sm font-medium text-muted-foreground">{label}</p>
      <div className="flex items-center justify-between gap-2">
        <p className="text-base">
          {value !== null ? `${value} ${suffix || ''}` : <span className="text-muted-foreground italic">{t('notSet')}</span>}
        </p>
        <Button 
          size="sm" 
          variant="ghost" 
          className="opacity-0 group-hover:opacity-100 transition-opacity h-6 w-6 p-0"
          onClick={() => setIsEditing(true)}
        >
          <Pencil className="h-3 w-3" />
        </Button>
      </div>
    </div>
  )
}

interface EditableTagsProps {
  values: string[]
  field: string
  label: string
  onSave: (field: string, values: string[]) => Promise<void>
  colorClass?: string
}

function EditableTags({ values, field, label, onSave, colorClass = "bg-primary/10 text-primary" }: EditableTagsProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [editValues, setEditValues] = useState<string[]>(values || [])
  const [newTag, setNewTag] = useState('')
  const [saving, setSaving] = useState(false)
  const t = useTranslations('profile')

  const handleAddTag = () => {
    if (newTag.trim() && !editValues.includes(newTag.trim())) {
      setEditValues([...editValues, newTag.trim()])
      setNewTag('')
    }
  }

  const handleRemoveTag = (tag: string) => {
    setEditValues(editValues.filter(t => t !== tag))
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await onSave(field, editValues)
      setIsEditing(false)
    } finally {
      setSaving(false)
    }
  }

  const handleCancel = () => {
    setEditValues(values || [])
    setNewTag('')
    setIsEditing(false)
  }

  if (isEditing) {
    return (
      <div className="space-y-2">
        <p className="text-sm font-medium text-muted-foreground">{label}</p>
        <div className="flex flex-wrap gap-2 mb-2">
          {editValues.map((tag, i) => (
            <span 
              key={i} 
              className={`px-2 py-1 ${colorClass} text-sm rounded flex items-center gap-1`}
            >
              {tag}
              <button 
                onClick={() => handleRemoveTag(tag)}
                className="hover:opacity-70"
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>
        <div className="flex gap-2">
          <Input
            value={newTag}
            onChange={(e) => setNewTag(e.target.value)}
            placeholder={t('addNewTag')}
            onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), handleAddTag())}
            className="flex-1"
          />
          <Button size="sm" variant="outline" onClick={handleAddTag}>
            <Plus className="h-3 w-3" />
          </Button>
        </div>
        <div className="flex gap-2 mt-2">
          <Button size="sm" onClick={handleSave} disabled={saving}>
            {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : <Save className="h-3 w-3" />}
            <span className="ml-1">{t('save')}</span>
          </Button>
          <Button size="sm" variant="outline" onClick={handleCancel} disabled={saving}>
            <X className="h-3 w-3" />
            <span className="ml-1">{t('cancel')}</span>
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="group">
      <div className="flex items-center justify-between mb-2">
        <p className="text-sm font-medium text-muted-foreground">{label}</p>
        <Button 
          size="sm" 
          variant="ghost" 
          className="opacity-0 group-hover:opacity-100 transition-opacity h-6 w-6 p-0"
          onClick={() => setIsEditing(true)}
        >
          <Pencil className="h-3 w-3" />
        </Button>
      </div>
      {values && values.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {values.map((tag, i) => (
            <span key={i} className={`px-2 py-1 ${colorClass} text-sm rounded`}>
              {tag}
            </span>
          ))}
        </div>
      ) : (
        <p className="text-muted-foreground italic text-sm">{t('notSet')}</p>
      )}
    </div>
  )
}

interface EditableSelectProps {
  value: string | null
  field: string
  label: string
  options: { value: string; label: string }[]
  onSave: (field: string, value: string) => Promise<void>
}

function EditableSelect({ value, field, label, options, onSave }: EditableSelectProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [editValue, setEditValue] = useState(value || '')
  const [saving, setSaving] = useState(false)
  const t = useTranslations('profile')

  const handleSave = async () => {
    setSaving(true)
    try {
      await onSave(field, editValue)
      setIsEditing(false)
    } finally {
      setSaving(false)
    }
  }

  const handleCancel = () => {
    setEditValue(value || '')
    setIsEditing(false)
  }

  const displayValue = options.find(o => o.value === value)?.label || value

  if (isEditing) {
    return (
      <div className="space-y-2">
        <p className="text-sm font-medium text-muted-foreground">{label}</p>
        <select
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        >
          <option value="">{t('selectOption')}</option>
          {options.map(opt => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
        <div className="flex gap-2">
          <Button size="sm" onClick={handleSave} disabled={saving}>
            {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : <Save className="h-3 w-3" />}
            <span className="ml-1">{t('save')}</span>
          </Button>
          <Button size="sm" variant="outline" onClick={handleCancel} disabled={saving}>
            <X className="h-3 w-3" />
            <span className="ml-1">{t('cancel')}</span>
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="group">
      <p className="text-sm font-medium text-muted-foreground">{label}</p>
      <div className="flex items-center justify-between gap-2">
        <p className="text-base font-medium capitalize">
          {displayValue || <span className="text-muted-foreground italic font-normal">{t('notSet')}</span>}
        </p>
        <Button 
          size="sm" 
          variant="ghost" 
          className="opacity-0 group-hover:opacity-100 transition-opacity h-6 w-6 p-0"
          onClick={() => setIsEditing(true)}
        >
          <Pencil className="h-3 w-3" />
        </Button>
      </div>
    </div>
  )
}

interface EditableBooleanProps {
  value: boolean | null
  field: string
  label: string
  trueLabel: string
  falseLabel: string
  onSave: (field: string, value: boolean) => Promise<void>
}

function EditableBoolean({ value, field, label, trueLabel, falseLabel, onSave }: EditableBooleanProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [editValue, setEditValue] = useState(value || false)
  const [saving, setSaving] = useState(false)
  const t = useTranslations('profile')

  const handleSave = async () => {
    setSaving(true)
    try {
      await onSave(field, editValue)
      setIsEditing(false)
    } finally {
      setSaving(false)
    }
  }

  const handleCancel = () => {
    setEditValue(value || false)
    setIsEditing(false)
  }

  if (isEditing) {
    return (
      <div className="space-y-2">
        <p className="text-sm font-medium text-muted-foreground">{label}</p>
        <div className="flex gap-2">
          <Button 
            size="sm" 
            variant={editValue ? "default" : "outline"}
            onClick={() => setEditValue(true)}
          >
            <Check className="h-3 w-3 mr-1" />
            {trueLabel}
          </Button>
          <Button 
            size="sm" 
            variant={!editValue ? "default" : "outline"}
            onClick={() => setEditValue(false)}
          >
            <X className="h-3 w-3 mr-1" />
            {falseLabel}
          </Button>
        </div>
        <div className="flex gap-2 mt-2">
          <Button size="sm" onClick={handleSave} disabled={saving}>
            {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : <Save className="h-3 w-3" />}
            <span className="ml-1">{t('save')}</span>
          </Button>
          <Button size="sm" variant="outline" onClick={handleCancel} disabled={saving}>
            <X className="h-3 w-3" />
            <span className="ml-1">{t('cancel')}</span>
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="group">
      <p className="text-sm font-medium text-muted-foreground">{label}</p>
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          {value ? (
            <>
              <Check className="h-4 w-4 text-green-500" />
              <span className="text-base">{trueLabel}</span>
            </>
          ) : (
            <>
              <X className="h-4 w-4 text-slate-400" />
              <span className="text-base text-muted-foreground">{falseLabel}</span>
            </>
          )}
        </div>
        <Button 
          size="sm" 
          variant="ghost" 
          className="opacity-0 group-hover:opacity-100 transition-opacity h-6 w-6 p-0"
          onClick={() => setIsEditing(true)}
        >
          <Pencil className="h-3 w-3" />
        </Button>
      </div>
    </div>
  )
}

export default function ProfilePage() {
  const router = useRouter()
  const supabase = createClientComponentClient()
  const t = useTranslations('profile')
  const tCommon = useTranslations('common')
  
  const [user, setUser] = useState<User | null>(null)
  const [profile, setProfile] = useState<SalesProfileData | null>(null)
  const [loading, setLoading] = useState(true)
  const [saveMessage, setSaveMessage] = useState<string | null>(null)

  const fetchProfile = useCallback(async () => {
    try {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) {
        router.push('/login')
        return
      }

      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/v1/profile/sales`,
        {
          headers: {
            'Authorization': `Bearer ${session.access_token}`
          }
        }
      )

      if (response.ok) {
        const data = await response.json()
        setProfile(data)
      } else if (response.status === 404) {
        router.push('/onboarding')
      }
    } catch (error) {
      console.error('Error fetching profile:', error)
    } finally {
      setLoading(false)
    }
  }, [supabase, router])

  useEffect(() => {
    const getUser = async () => {
      const { data: { user } } = await supabase.auth.getUser()
      setUser(user)
    }
    getUser()
    fetchProfile()
  }, [supabase, fetchProfile])

  // Generic save function for any field
  const handleSaveField = async (field: string, value: any) => {
    const { data: { session } } = await supabase.auth.getSession()
    if (!session) return

    const response = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL}/api/v1/profile/sales`,
      {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${session.access_token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ [field]: value })
      }
    )

    if (response.ok) {
      const updated = await response.json()
      setProfile(updated)
      setSaveMessage(t('fieldSaved'))
      setTimeout(() => setSaveMessage(null), 2000)
    } else {
      throw new Error('Failed to save')
    }
  }

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-50 dark:bg-slate-900">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    )
  }

  if (!profile) {
    return (
      <DashboardLayout user={user}>
        <div className="p-6 lg:p-8 max-w-4xl mx-auto">
          <div className="text-center py-16">
            <UserIcon className="h-16 w-16 mx-auto text-slate-200 dark:text-slate-700 mb-4" />
            <h2 className="text-2xl font-bold mb-2 text-slate-900 dark:text-white">{t('noProfile')}</h2>
            <p className="text-slate-500 dark:text-slate-400 mb-6">
              {t('startOnboarding')}
            </p>
            <Button onClick={() => router.push('/onboarding')}>
              {t('startOnboardingBtn')}
            </Button>
          </div>
        </div>
      </DashboardLayout>
    )
  }

  return (
    <DashboardLayout user={user}>
      <div className="p-6 lg:p-8 max-w-4xl mx-auto animate-fade-in">
        {/* Save Message Toast */}
        {saveMessage && (
          <div className="fixed top-4 right-4 z-50 bg-green-600 text-white px-4 py-2 rounded-lg shadow-lg flex items-center gap-2 animate-fade-in">
            <Check className="h-4 w-4" />
            {saveMessage}
          </div>
        )}

        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div className="group flex-1">
              <EditableText
                value={profile.full_name}
                field="full_name"
                label=""
                onSave={handleSaveField}
                placeholder={t('yourName')}
              />
              <div className="mt-1">
                <EditableText
                  value={profile.role}
                  field="role"
                  label=""
                  onSave={handleSaveField}
                  placeholder={t('yourRole')}
                />
              </div>
            </div>
            <div className="flex gap-2 ml-4">
              <Button onClick={() => router.push('/onboarding/chat')} className="bg-gradient-to-r from-violet-600 to-fuchsia-600 hover:from-violet-700 hover:to-fuchsia-700">
                <Wand2 className="h-4 w-4 mr-2" />
                {t('refreshWithAI')}
              </Button>
            </div>
          </div>
        </div>

        {/* Profile Completeness */}
        <Card className="mb-6">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-slate-700 dark:text-slate-200">{t('completeness')}</span>
              <span className="text-sm font-bold text-slate-900 dark:text-white">{profile.profile_completeness}%</span>
            </div>
            <div className="h-2 bg-gray-200 dark:bg-slate-700 rounded-full overflow-hidden">
              <div 
                className={`h-full transition-all ${
                  profile.profile_completeness >= 80 ? 'bg-green-500' :
                  profile.profile_completeness >= 50 ? 'bg-yellow-500' :
                  'bg-red-500'
                }`}
                style={{ width: `${profile.profile_completeness}%` }}
              />
            </div>
            <p className="text-xs text-muted-foreground mt-2">{t('editHint')}</p>
          </CardContent>
        </Card>

        {/* My Story - Sales Narrative */}
        {profile.sales_narrative && (
          <Card className="mb-6 border-primary/20 bg-gradient-to-br from-primary/5 to-transparent">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BookOpen className="h-5 w-5 text-primary" />
                {t('myStory')}
              </CardTitle>
              <CardDescription>
                {t('myStoryDesc')}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <EditableText
                value={profile.sales_narrative}
                field="sales_narrative"
                label=""
                onSave={handleSaveField}
                multiline
              />
            </CardContent>
          </Card>
        )}

        {/* Quick Summary */}
        {profile.ai_summary && !profile.sales_narrative && (
          <Card className="mb-6">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BookOpen className="h-5 w-5" />
                {t('summary')}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <EditableText
                value={profile.ai_summary}
                field="ai_summary"
                label=""
                onSave={handleSaveField}
                multiline
              />
            </CardContent>
          </Card>
        )}

        <div className="grid gap-6 md:grid-cols-2">
          {/* Professional Info */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Briefcase className="h-5 w-5" />
                {t('sections.experience')}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <EditableNumber
                value={profile.experience_years}
                field="experience_years"
                label={t('fields.yearsExperience')}
                suffix={t('years')}
                onSave={handleSaveField}
              />
              <EditableText
                value={profile.sales_methodology}
                field="sales_methodology"
                label={t('fields.sellingStyle')}
                onSave={handleSaveField}
              />
              {profile.methodology_description && (
                <EditableText
                  value={profile.methodology_description}
                  field="methodology_description"
                  label={t('approach')}
                  onSave={handleSaveField}
                  multiline
                />
              )}
              <EditableText
                value={profile.communication_style}
                field="communication_style"
                label={t('fields.communicationPreference')}
                onSave={handleSaveField}
              />
            </CardContent>
          </Card>

          {/* Strengths */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Award className="h-5 w-5" />
                {t('strengthsTitle')}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <EditableTags
                values={profile.strengths || []}
                field="strengths"
                label={t('strengths')}
                onSave={handleSaveField}
                colorClass="bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400"
              />
              <EditableTags
                values={profile.areas_to_improve || []}
                field="areas_to_improve"
                label={t('weaknesses')}
                onSave={handleSaveField}
                colorClass="bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400"
              />
            </CardContent>
          </Card>

          {/* Target Market */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Target className="h-5 w-5" />
                {t('sections.targetMarket')}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <EditableTags
                values={profile.target_industries || []}
                field="target_industries"
                label={t('fields.industries')}
                onSave={handleSaveField}
                colorClass="bg-primary/10 text-primary"
              />
              <EditableTags
                values={profile.target_regions || []}
                field="target_regions"
                label={t('fields.regions')}
                onSave={handleSaveField}
                colorClass="bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400"
              />
              <EditableTags
                values={profile.target_company_sizes || []}
                field="target_company_sizes"
                label={t('fields.companySizes')}
                onSave={handleSaveField}
                colorClass="bg-gray-100 dark:bg-slate-700 text-gray-700 dark:text-slate-300"
              />
            </CardContent>
          </Card>

          {/* Goals & Preferences */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <RefreshCw className="h-5 w-5" />
                {t('sections.goalsPrefs')}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <EditableText
                value={profile.quarterly_goals}
                field="quarterly_goals"
                label={t('fields.quarterlyGoals')}
                onSave={handleSaveField}
                multiline
              />
              <EditableTags
                values={profile.preferred_meeting_types || []}
                field="preferred_meeting_types"
                label={t('fields.meetingTypes')}
                onSave={handleSaveField}
                colorClass="bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-400"
              />
            </CardContent>
          </Card>
        </div>

        {/* Communication & Email Style - Full Width */}
        <Card className="mt-6 border-violet-200/50 dark:border-violet-800/50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Mail className="h-5 w-5 text-violet-600" />
              {t('communicationStyle.title')}
            </CardTitle>
            <CardDescription>
              {t('communicationStyle.description')}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
              <EditableSelect
                value={profile.email_tone || profile.style_guide?.tone || 'professional'}
                field="email_tone"
                label={t('communicationStyle.writingTone')}
                options={[
                  { value: 'professional', label: t('communicationStyle.toneProfessional') },
                  { value: 'direct', label: t('communicationStyle.toneDirect') },
                  { value: 'warm', label: t('communicationStyle.toneWarm') },
                  { value: 'formal', label: t('communicationStyle.toneFormal') },
                  { value: 'casual', label: t('communicationStyle.toneCasual') }
                ]}
                onSave={handleSaveField}
              />
              
              <EditableSelect
                value={profile.writing_length_preference || profile.style_guide?.writing_length || 'concise'}
                field="writing_length_preference"
                label={t('communicationStyle.messageLength')}
                options={[
                  { value: 'concise', label: t('communicationStyle.concise') },
                  { value: 'detailed', label: t('communicationStyle.detailed') }
                ]}
                onSave={handleSaveField}
              />
              
              <EditableBoolean
                value={profile.uses_emoji ?? profile.style_guide?.emoji_usage ?? false}
                field="uses_emoji"
                label={t('communicationStyle.emojiUsage')}
                trueLabel={t('communicationStyle.emojiYes')}
                falseLabel={t('communicationStyle.emojiNo')}
                onSave={handleSaveField}
              />
              
              <EditableText
                value={profile.email_signoff || profile.style_guide?.signoff || 'Kind regards'}
                field="email_signoff"
                label={t('communicationStyle.emailSignoff')}
                onSave={handleSaveField}
              />
            </div>
            
            {/* Persuasion Style */}
            {profile.style_guide?.persuasion_style && (
              <div className="mt-6 pt-6 border-t border-slate-200 dark:border-slate-700">
                <div className="flex items-start gap-3">
                  <Sparkles className="h-5 w-5 text-violet-500 mt-0.5" />
                  <div>
                    <p className="text-sm font-medium text-muted-foreground mb-1">{t('communicationStyle.persuasionStyle')}</p>
                    <p className="text-base text-slate-700 dark:text-slate-300">
                      {profile.style_guide.persuasion_style === 'logic' && t('communicationStyle.persuasionLogic')}
                      {profile.style_guide.persuasion_style === 'story' && t('communicationStyle.persuasionStory')}
                      {profile.style_guide.persuasion_style === 'reference' && t('communicationStyle.persuasionReference')}
                      {profile.style_guide.persuasion_style === 'authority' && t('communicationStyle.persuasionAuthority')}
                    </p>
                  </div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* How this is used */}
        <Card className="mt-6 bg-muted/50">
          <CardContent className="pt-6">
            <h3 className="font-semibold mb-2">{t('howUsed.title')}</h3>
            <ul className="text-sm text-muted-foreground space-y-1">
              <li>• <strong>{t('howUsed.prep')}:</strong> {t('howUsed.prepDesc')}</li>
              <li>• <strong>{t('howUsed.followup')}:</strong> {t('howUsed.followupDesc')}</li>
              <li>• <strong>{t('howUsed.research')}:</strong> {t('howUsed.researchDesc')}</li>
            </ul>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  )
}
