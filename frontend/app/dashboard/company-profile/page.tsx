'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { createClientComponentClient } from '@supabase/auth-helpers-nextjs'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { DashboardLayout } from '@/components/layout'
import { 
  ArrowLeft, 
  Building2, 
  Package, 
  Target, 
  Users,
  Trophy,
  Edit,
  Loader2,
  BookOpen,
  Zap,
  TrendingUp
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

export default function CompanyProfilePage() {
  const router = useRouter()
  const supabase = createClientComponentClient()
  const t = useTranslations('companyProfile')
  const tCommon = useTranslations('common')
  
  const [user, setUser] = useState<User | null>(null)
  const [profile, setProfile] = useState<CompanyProfile | null>(null)
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
          // No profile yet
          setProfile(null)
        }
      } catch (error) {
        console.error('Error fetching company profile:', error)
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
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl lg:text-3xl font-bold text-slate-900 dark:text-white">{profile.company_name}</h1>
              <p className="text-slate-500 dark:text-slate-400 mt-1">
              {profile.industry || 'Bedrijfsprofiel'}
            </p>
          </div>
          <Button onClick={() => router.push('/onboarding/company')}>
            <Edit className="h-4 w-4 mr-2" />
            {t('edit')}
          </Button>
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
            <div className="prose prose-sm max-w-none dark:prose-invert">
              {profile.company_narrative.split('\n\n').map((paragraph, idx) => (
                <p key={idx} className="text-gray-700 dark:text-slate-300 leading-relaxed mb-4">
                  {paragraph}
                </p>
              ))}
            </div>
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
            <p className="text-gray-700 dark:text-slate-300">{profile.ai_summary}</p>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-6 md:grid-cols-2">
        {/* Products & Services */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Package className="h-5 w-5" />
              Producten & Diensten
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
            {profile.core_value_props && profile.core_value_props.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {profile.core_value_props.map((prop, i) => (
                  <span 
                    key={i} 
                    className="px-3 py-1 bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 text-sm rounded-full"
                  >
                    {prop}
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-muted-foreground text-sm">{t('notSet')}</p>
            )}
            
            {profile.differentiators && profile.differentiators.length > 0 && (
              <div>
                <p className="text-sm font-medium text-muted-foreground mb-2">{t('sections.differentiators')}</p>
                <div className="flex flex-wrap gap-2">
                  {profile.differentiators.map((diff, i) => (
                    <span 
                      key={i} 
                      className="px-3 py-1 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 text-sm rounded-full"
                    >
                      {diff}
                    </span>
                  ))}
                </div>
              </div>
            )}
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
            {profile.ideal_customer_profile ? (
              <>
                {profile.ideal_customer_profile.industries?.length > 0 && (
                  <div>
                    <p className="text-sm font-medium text-muted-foreground mb-2">{t('fields.industries')}</p>
                    <div className="flex flex-wrap gap-2">
                      {profile.ideal_customer_profile.industries.map((ind, i) => (
                        <span key={i} className="px-2 py-1 bg-primary/10 text-primary text-sm rounded">
                          {ind}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {profile.ideal_customer_profile.company_sizes?.length > 0 && (
                  <div>
                    <p className="text-sm font-medium text-muted-foreground mb-2">{t('fields.companySizes')}</p>
                    <div className="flex flex-wrap gap-2">
                      {profile.ideal_customer_profile.company_sizes.map((size, i) => (
                        <span key={i} className="px-2 py-1 bg-gray-100 dark:bg-slate-700 text-gray-700 dark:text-slate-300 text-sm rounded">
                          {size}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {profile.ideal_customer_profile.pain_points?.length > 0 && (
                  <div>
                    <p className="text-sm font-medium text-muted-foreground mb-2">{t('fields.painPoints')}</p>
                    <ul className="text-sm text-gray-700 dark:text-slate-300 space-y-1">
                      {profile.ideal_customer_profile.pain_points.map((point, i) => (
                        <li key={i}>• {point}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </>
            ) : (
              <p className="text-muted-foreground text-sm">{t('notSet')}</p>
            )}
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
                      <strong>Resultaat:</strong> {cs.results}
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
            {profile.typical_sales_cycle && (
              <div>
                <p className="text-sm font-medium text-muted-foreground">{t('fields.salesCycle')}</p>
                <p className="text-base">{profile.typical_sales_cycle}</p>
              </div>
            )}
            {profile.average_deal_size && (
              <div>
                <p className="text-sm font-medium text-muted-foreground">{t('fields.avgDeal')}</p>
                <p className="text-base">{profile.average_deal_size}</p>
              </div>
            )}
            {profile.competitors && profile.competitors.length > 0 && (
              <div>
                <p className="text-sm font-medium text-muted-foreground mb-2">{t('fields.competitors')}</p>
                <div className="flex flex-wrap gap-2">
                  {profile.competitors.map((comp, i) => (
                    <span key={i} className="px-2 py-1 bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 text-sm rounded">
                      {comp}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {profile.competitive_advantages && (
              <div>
                <p className="text-sm font-medium text-muted-foreground">{t('fields.competitiveAdvantage')}</p>
                <p className="text-base text-gray-700 dark:text-slate-300">{profile.competitive_advantages}</p>
              </div>
            )}
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

