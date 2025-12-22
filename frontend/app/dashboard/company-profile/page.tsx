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
  Building2, 
  Package, 
  Target, 
  Users,
  Trophy,
  Loader2,
  BookOpen,
  Zap,
  TrendingUp,
  Wand2,
  Pencil,
  Save,
  X,
  Plus,
  Check
} from 'lucide-react'
import { useTranslations } from 'next-intl'
import type { User } from '@supabase/supabase-js'

interface Product {
  name: string
  description: string
  value_proposition: string
  target_persona?: string
}

interface BuyerPersona {
  title: string
  seniority: string
  pain_points: string[]
  goals: string[]
  objections: string[]
}

interface CaseStudy {
  customer: string
  industry: string
  challenge: string
  solution: string
  results: string
}

interface ICP {
  industries: string[]
  company_sizes: string[]
  regions: string[]
  pain_points: string[]
  buying_triggers: string[]
}

interface CompanyProfile {
  id: string
  organization_id: string
  company_name: string
  industry: string | null
  company_size: string | null
  headquarters: string | null
  website: string | null
  products: Product[]
  core_value_props: string[]
  differentiators: string[]
  unique_selling_points: string | null
  ideal_customer_profile: ICP | null
  buyer_personas: BuyerPersona[]
  case_studies: CaseStudy[]
  competitors: string[]
  competitive_advantages: string | null
  typical_sales_cycle: string | null
  average_deal_size: string | null
  ai_summary: string | null
  company_narrative: string | null
  profile_completeness: number
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
  const t = useTranslations('companyProfile')

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
        {label && <p className="text-sm font-medium text-muted-foreground">{label}</p>}
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
      {label && <p className="text-sm font-medium text-muted-foreground">{label}</p>}
      <div className="flex items-start justify-between gap-2">
        <p className="text-base text-gray-700 dark:text-slate-300">
          {value || <span className="text-muted-foreground italic">{t('notSet')}</span>}
        </p>
        <Button 
          size="sm" 
          variant="ghost" 
          className="opacity-0 group-hover:opacity-100 transition-opacity h-6 w-6 p-0 shrink-0"
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
  const t = useTranslations('companyProfile')

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
            placeholder={t('addNew')}
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

interface EditableICPFieldProps {
  icp: ICP | null
  fieldKey: keyof ICP
  label: string
  onSave: (field: string, value: ICP) => Promise<void>
  colorClass?: string
}

function EditableICPField({ icp, fieldKey, label, onSave, colorClass = "bg-primary/10 text-primary" }: EditableICPFieldProps) {
  const values = icp?.[fieldKey] || []
  
  const handleSave = async (field: string, newValues: string[]) => {
    const updatedICP: ICP = {
      industries: icp?.industries || [],
      company_sizes: icp?.company_sizes || [],
      regions: icp?.regions || [],
      pain_points: icp?.pain_points || [],
      buying_triggers: icp?.buying_triggers || [],
      [fieldKey]: newValues
    }
    await onSave('ideal_customer_profile', updatedICP)
  }
  
  return (
    <EditableTags
      values={values as string[]}
      field={fieldKey}
      label={label}
      onSave={handleSave}
      colorClass={colorClass}
    />
  )
}

export default function CompanyProfilePage() {
  const router = useRouter()
  const supabase = createClientComponentClient()
  const t = useTranslations('companyProfile')
  
  const [user, setUser] = useState<User | null>(null)
  const [profile, setProfile] = useState<CompanyProfile | null>(null)
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
        `${process.env.NEXT_PUBLIC_API_URL}/api/v1/profile/company`,
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
        setProfile(null)
      }
    } catch (error) {
      console.error('Error fetching company profile:', error)
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
      `${process.env.NEXT_PUBLIC_API_URL}/api/v1/profile/company`,
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
            <Building2 className="h-16 w-16 mx-auto text-slate-200 dark:text-slate-700 mb-4" />
            <h2 className="text-2xl font-bold mb-2 text-slate-900 dark:text-white">{t('noProfile')}</h2>
            <p className="text-slate-500 dark:text-slate-400 mb-6">
              {t('noProfileDesc')}
            </p>
            <Button onClick={() => router.push('/onboarding/company')}>
              <Building2 className="h-4 w-4 mr-2" />
              {t('createProfile')}
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
            <div className="flex-1">
              <div className="group">
                <EditableText
                  value={profile.company_name}
                  field="company_name"
                  label=""
                  onSave={handleSaveField}
                  placeholder={t('companyName')}
                />
              </div>
              <div className="mt-1">
                <EditableText
                  value={profile.industry}
                  field="industry"
                  label=""
                  onSave={handleSaveField}
                  placeholder={t('industry')}
                />
              </div>
            </div>
            <div className="flex gap-2 ml-4">
              <Button onClick={() => router.push('/onboarding/company/magic')} className="bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700">
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

        {/* Company Story - Narrative */}
        {profile.company_narrative && (
          <Card className="mb-6 border-primary/20 bg-gradient-to-br from-primary/5 to-transparent">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BookOpen className="h-5 w-5 text-primary" />
                {t('ourStory')}
              </CardTitle>
              <CardDescription>
                {t('ourStoryDesc')}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <EditableText
                value={profile.company_narrative}
                field="company_narrative"
                label=""
                onSave={handleSaveField}
                multiline
              />
            </CardContent>
          </Card>
        )}

        {/* Quick Summary */}
        {profile.ai_summary && !profile.company_narrative && (
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
          {/* Products & Services */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Package className="h-5 w-5" />
                {t('sections.products')}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {profile.products && profile.products.length > 0 ? (
                profile.products.map((product, i) => (
                  <div key={i} className="p-3 bg-gray-50 dark:bg-slate-800 rounded-lg">
                    <h4 className="font-medium text-slate-900 dark:text-white">{product.name}</h4>
                    {product.description && (
                      <p className="text-sm text-gray-600 dark:text-slate-400 mt-1">{product.description}</p>
                    )}
                    {product.value_proposition && (
                      <p className="text-sm text-primary mt-1">
                        <strong>Value:</strong> {product.value_proposition}
                      </p>
                    )}
                  </div>
                ))
              ) : (
                <p className="text-muted-foreground text-sm">{t('noProducts')}</p>
              )}
            </CardContent>
          </Card>

          {/* Value Propositions */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Zap className="h-5 w-5" />
                {t('sections.valueProps')}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <EditableTags
                values={profile.core_value_props || []}
                field="core_value_props"
                label={t('fields.valueProps')}
                onSave={handleSaveField}
                colorClass="bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400"
              />
              <EditableTags
                values={profile.differentiators || []}
                field="differentiators"
                label={t('sections.differentiators')}
                onSave={handleSaveField}
                colorClass="bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400"
              />
            </CardContent>
          </Card>

          {/* Ideal Customer Profile */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Target className="h-5 w-5" />
                {t('sections.icp')}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <EditableICPField
                icp={profile.ideal_customer_profile}
                fieldKey="industries"
                label={t('fields.industries')}
                onSave={handleSaveField}
                colorClass="bg-primary/10 text-primary"
              />
              <EditableICPField
                icp={profile.ideal_customer_profile}
                fieldKey="company_sizes"
                label={t('fields.companySizes')}
                onSave={handleSaveField}
                colorClass="bg-gray-100 dark:bg-slate-700 text-gray-700 dark:text-slate-300"
              />
              <EditableICPField
                icp={profile.ideal_customer_profile}
                fieldKey="pain_points"
                label={t('fields.painPoints')}
                onSave={handleSaveField}
                colorClass="bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-400"
              />
            </CardContent>
          </Card>

          {/* Buyer Personas */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Users className="h-5 w-5" />
                {t('sections.personas')}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {profile.buyer_personas && profile.buyer_personas.length > 0 ? (
                profile.buyer_personas.map((persona, i) => (
                  <div key={i} className="p-3 bg-gray-50 dark:bg-slate-800 rounded-lg">
                    <h4 className="font-medium text-slate-900 dark:text-white">{persona.title}</h4>
                    <p className="text-sm text-muted-foreground">{persona.seniority}</p>
                    {persona.pain_points?.length > 0 && (
                      <div className="mt-2">
                        <p className="text-xs font-medium text-muted-foreground">{t('fields.painPoints')}:</p>
                        <p className="text-sm text-gray-700 dark:text-slate-300">{persona.pain_points.join(', ')}</p>
                      </div>
                    )}
                  </div>
                ))
              ) : (
                <p className="text-muted-foreground text-sm">{t('noPersonas')}</p>
              )}
            </CardContent>
          </Card>

          {/* Case Studies */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Trophy className="h-5 w-5" />
                {t('sections.caseStudies')}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {profile.case_studies && profile.case_studies.length > 0 ? (
                profile.case_studies.map((cs, i) => (
                  <div key={i} className="p-3 bg-gray-50 dark:bg-slate-800 rounded-lg">
                    <h4 className="font-medium text-slate-900 dark:text-white">{cs.customer}</h4>
                    <p className="text-sm text-muted-foreground">{cs.industry}</p>
                    {cs.results && (
                      <p className="text-sm text-green-700 dark:text-green-400 mt-1">
                        <strong>{t('fields.result')}:</strong> {cs.results}
                      </p>
                    )}
                  </div>
                ))
              ) : (
                <p className="text-muted-foreground text-sm">{t('noCaseStudies')}</p>
              )}
            </CardContent>
          </Card>

          {/* Sales Info */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <TrendingUp className="h-5 w-5" />
                {t('sections.salesInfo')}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <EditableText
                value={profile.typical_sales_cycle}
                field="typical_sales_cycle"
                label={t('fields.salesCycle')}
                onSave={handleSaveField}
              />
              <EditableText
                value={profile.average_deal_size}
                field="average_deal_size"
                label={t('fields.avgDeal')}
                onSave={handleSaveField}
              />
              <EditableTags
                values={profile.competitors || []}
                field="competitors"
                label={t('fields.competitors')}
                onSave={handleSaveField}
                colorClass="bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400"
              />
              <EditableText
                value={profile.competitive_advantages}
                field="competitive_advantages"
                label={t('fields.competitiveAdvantage')}
                onSave={handleSaveField}
                multiline
              />
            </CardContent>
          </Card>
        </div>

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
