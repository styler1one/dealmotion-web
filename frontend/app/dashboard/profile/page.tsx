'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { createClientComponentClient } from '@supabase/auth-helpers-nextjs'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { DashboardLayout } from '@/components/layout'
import { 
  ArrowLeft, 
  User as UserIcon, 
  Briefcase, 
  Target, 
  Award,
  Edit,
  RefreshCw,
  Loader2,
  BookOpen,
  Wand2,
  Mail,
  MessageSquare,
  Sparkles,
  Check,
  X
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
  // Email & Communication preferences
  email_tone: string | null
  uses_emoji: boolean | null
  email_signoff: string | null
  writing_length_preference: string | null
  style_guide: StyleGuide | null
  created_at: string
  updated_at: string
}

export default function ProfilePage() {
  const router = useRouter()
  const supabase = createClientComponentClient()
  const t = useTranslations('profile')
  const tCommon = useTranslations('common')
  
  const [user, setUser] = useState<User | null>(null)
  const [profile, setProfile] = useState<SalesProfileData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const getUser = async () => {
      const { data: { user } } = await supabase.auth.getUser()
      setUser(user)
    }
    getUser()
    const fetchProfile = async () => {
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
          // No profile yet, redirect to onboarding
          router.push('/onboarding')
        }
      } catch (error) {
        console.error('Error fetching profile:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchProfile()
  }, [supabase, router])

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
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl lg:text-3xl font-bold text-slate-900 dark:text-white">{profile.full_name}</h1>
              <p className="text-slate-500 dark:text-slate-400 mt-1">
                {profile.role || 'Sales Professional'}
              </p>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => router.push('/onboarding')}>
                <Edit className="h-4 w-4 mr-2" />
                {t('edit')}
              </Button>
              <Button onClick={() => router.push('/onboarding/chat')} className="bg-gradient-to-r from-violet-600 to-fuchsia-600 hover:from-violet-700 hover:to-fuchsia-700">
                <Wand2 className="h-4 w-4 mr-2" />
                Refresh with AI
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
            <div className="prose prose-sm max-w-none dark:prose-invert">
              {profile.sales_narrative.split('\n\n').map((paragraph, idx) => (
                <p key={idx} className="text-gray-700 dark:text-slate-300 leading-relaxed mb-4">
                  {paragraph}
                </p>
              ))}
            </div>
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
            <p className="text-gray-700 dark:text-slate-300">{profile.ai_summary}</p>
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
            <div>
              <p className="text-sm font-medium text-muted-foreground">{t('fields.yearsExperience')}</p>
              <p className="text-base">
                {profile.experience_years ? `${profile.experience_years} ${t('years')}` : t('notSet')}
              </p>
            </div>
            <div>
              <p className="text-sm font-medium text-muted-foreground">{t('fields.sellingStyle')}</p>
              <p className="text-base">{profile.sales_methodology || t('notSet')}</p>
            </div>
            {profile.methodology_description && (
              <div>
                <p className="text-sm font-medium text-muted-foreground">{t('approach')}</p>
                <p className="text-base text-gray-700 dark:text-slate-300">{profile.methodology_description}</p>
              </div>
            )}
            <div>
              <p className="text-sm font-medium text-muted-foreground">{t('fields.communicationPreference')}</p>
              <p className="text-base">{profile.communication_style || t('notSet')}</p>
            </div>
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
            {profile.strengths && profile.strengths.length > 0 && (
              <div>
                <p className="text-sm font-medium text-muted-foreground mb-2">{t('strengths')}</p>
                <div className="flex flex-wrap gap-2">
                  {profile.strengths.map((strength, i) => (
                    <span 
                      key={i} 
                      className="px-2 py-1 bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 text-sm rounded"
                    >
                      {strength}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {profile.areas_to_improve && profile.areas_to_improve.length > 0 && (
              <div>
                <p className="text-sm font-medium text-muted-foreground mb-2">{t('weaknesses')}</p>
                <div className="flex flex-wrap gap-2">
                  {profile.areas_to_improve.map((area, i) => (
                    <span 
                      key={i} 
                      className="px-2 py-1 bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400 text-sm rounded"
                    >
                      {area}
                    </span>
                  ))}
                </div>
              </div>
            )}
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
            {profile.target_industries && profile.target_industries.length > 0 && (
              <div>
                <p className="text-sm font-medium text-muted-foreground mb-2">{t('fields.industries')}</p>
                <div className="flex flex-wrap gap-2">
                  {profile.target_industries.map((industry, i) => (
                    <span 
                      key={i} 
                      className="px-2 py-1 bg-primary/10 text-primary text-sm rounded"
                    >
                      {industry}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {profile.target_regions && profile.target_regions.length > 0 && (
              <div>
                <p className="text-sm font-medium text-muted-foreground mb-2">{t('fields.regions')}</p>
                <div className="flex flex-wrap gap-2">
                  {profile.target_regions.map((region, i) => (
                    <span 
                      key={i} 
                      className="px-2 py-1 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 text-sm rounded"
                    >
                      {region}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {profile.target_company_sizes && profile.target_company_sizes.length > 0 && (
              <div>
                <p className="text-sm font-medium text-muted-foreground mb-2">{t('fields.companySizes')}</p>
                <div className="flex flex-wrap gap-2">
                  {profile.target_company_sizes.map((size, i) => (
                    <span 
                      key={i} 
                      className="px-2 py-1 bg-gray-100 dark:bg-slate-700 text-gray-700 dark:text-slate-300 text-sm rounded"
                    >
                      {size}
                    </span>
                  ))}
                </div>
              </div>
            )}
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
            {profile.quarterly_goals && (
              <div>
                <p className="text-sm font-medium text-muted-foreground">{t('fields.quarterlyGoals')}</p>
                <p className="text-base text-gray-700 dark:text-slate-300">{profile.quarterly_goals}</p>
              </div>
            )}
            {profile.preferred_meeting_types && profile.preferred_meeting_types.length > 0 && (
              <div>
                <p className="text-sm font-medium text-muted-foreground mb-2">{t('fields.meetingTypes')}</p>
                <div className="flex flex-wrap gap-2">
                  {profile.preferred_meeting_types.map((type, i) => (
                    <span 
                      key={i} 
                      className="px-2 py-1 bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-400 text-sm rounded"
                    >
                      {type}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Communication & Email Style - Full Width */}
      {(profile.email_tone || profile.email_signoff || profile.style_guide) && (
        <Card className="mt-6 border-violet-200/50 dark:border-violet-800/50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Mail className="h-5 w-5 text-violet-600" />
              Communicatiestijl & Email Voorkeuren
            </CardTitle>
            <CardDescription>
              Zo schrijft DealMotion emails en berichten namens jou
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
              {/* Email Tone */}
              <div className="space-y-1">
                <p className="text-sm font-medium text-muted-foreground">Schrijftoon</p>
                <p className="text-base font-medium capitalize">
                  {profile.email_tone || profile.style_guide?.tone || 'Professioneel'}
                </p>
              </div>
              
              {/* Writing Length */}
              <div className="space-y-1">
                <p className="text-sm font-medium text-muted-foreground">Berichtlengte</p>
                <p className="text-base font-medium capitalize">
                  {profile.writing_length_preference === 'concise' ? 'Kort & bondig' :
                   profile.writing_length_preference === 'detailed' ? 'Uitgebreid' :
                   profile.style_guide?.writing_length === 'concise' ? 'Kort & bondig' :
                   profile.style_guide?.writing_length === 'detailed' ? 'Uitgebreid' :
                   'Standaard'}
                </p>
              </div>
              
              {/* Emoji Usage */}
              <div className="space-y-1">
                <p className="text-sm font-medium text-muted-foreground">Emoji gebruik</p>
                <div className="flex items-center gap-2">
                  {(profile.uses_emoji || profile.style_guide?.emoji_usage) ? (
                    <>
                      <Check className="h-4 w-4 text-green-500" />
                      <span className="text-base">Ja, in emails</span>
                    </>
                  ) : (
                    <>
                      <X className="h-4 w-4 text-slate-400" />
                      <span className="text-base text-muted-foreground">Nee</span>
                    </>
                  )}
                </div>
              </div>
              
              {/* Email Signoff */}
              <div className="space-y-1">
                <p className="text-sm font-medium text-muted-foreground">Email afsluiting</p>
                <p className="text-base font-medium">
                  {profile.email_signoff || profile.style_guide?.signoff || 'Met vriendelijke groet'}
                </p>
              </div>
            </div>
            
            {/* Persuasion Style - if available */}
            {profile.style_guide?.persuasion_style && (
              <div className="mt-6 pt-6 border-t border-slate-200 dark:border-slate-700">
                <div className="flex items-start gap-3">
                  <Sparkles className="h-5 w-5 text-violet-500 mt-0.5" />
                  <div>
                    <p className="text-sm font-medium text-muted-foreground mb-1">Overtuigingsstijl</p>
                    <p className="text-base text-slate-700 dark:text-slate-300">
                      {profile.style_guide.persuasion_style === 'logic' && 'Logica & data - Overtuigt met feiten, cijfers en rationele argumenten'}
                      {profile.style_guide.persuasion_style === 'story' && 'Storytelling - Overtuigt met verhalen, voorbeelden en emotie'}
                      {profile.style_guide.persuasion_style === 'reference' && 'Social proof - Overtuigt met referenties, cases en testimonials'}
                      {profile.style_guide.persuasion_style === 'authority' && 'Autoriteit - Overtuigt met expertise en thought leadership'}
                    </p>
                  </div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

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

