'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { createClientComponentClient } from '@supabase/auth-helpers-nextjs'
import { useTranslations, useLocale } from 'next-intl'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { useToast } from '@/components/ui/use-toast'
import { LanguageSelector } from '@/components/language-selector'
import type { Locale } from '@/i18n/config'
import { 
  ArrowLeft, 
  ArrowRight, 
  Sparkles,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Linkedin,
  User,
  Briefcase,
  Target,
  MessageSquare,
  Edit3,
  Wand2
} from 'lucide-react'

type WizardStep = 'input' | 'generating' | 'review' | 'saving' | 'complete'

interface FieldSource {
  value: any
  source: string
  confidence: number
  editable: boolean
  required: boolean
}

interface MagicStartResponse {
  session_id: string
  status: string
  message: string
}

interface MagicStatusResponse {
  session_id: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  profile_data?: Record<string, any>
  field_sources?: Record<string, FieldSource>
  missing_fields?: string[]
  linkedin_data?: Record<string, any>
  error?: string
}

interface MagicResult {
  success: boolean
  profile_data: Record<string, any>
  field_sources: Record<string, FieldSource>
  missing_fields: string[]
  linkedin_data: Record<string, any>
  error?: string
}

export default function MagicOnboardingPage() {
  const router = useRouter()
  const supabase = createClientComponentClient()
  const { toast } = useToast()
  const t = useTranslations('onboarding')
  const locale = useLocale() as Locale
  
  const [step, setStep] = useState<WizardStep>('input')
  const [linkedinUrl, setLinkedinUrl] = useState('')
  const [userName, setUserName] = useState('')
  const [companyName, setCompanyName] = useState('')
  const [loading, setLoading] = useState(false)
  const [magicResult, setMagicResult] = useState<MagicResult | null>(null)
  const [editedProfile, setEditedProfile] = useState<Record<string, any>>({})
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['identity', 'approach']))
  const [isRefresh, setIsRefresh] = useState(false)
  const [existingProfile, setExistingProfile] = useState<Record<string, any> | null>(null)
  const [checkingProfile, setCheckingProfile] = useState(true)

  // Check for existing profile on mount
  useEffect(() => {
    checkExistingProfile()
  }, [])

  const checkExistingProfile = async () => {
    setCheckingProfile(true)
    try {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) {
        router.push('/login')
        return
      }

      // Pre-fill name from session if available
      if (session.user?.email) {
        const emailName = session.user.email.split('@')[0]
        setUserName(emailName.split('.').map(s => s.charAt(0).toUpperCase() + s.slice(1)).join(' '))
      }

      // Check if user already has a sales profile
      const profileResponse = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/v1/profile/sales`,
        {
          headers: {
            'Authorization': `Bearer ${session.access_token}`
          }
        }
      )

      if (profileResponse.ok) {
        const profileData = await profileResponse.json()
        if (profileData && profileData.id) {
          setExistingProfile(profileData)
          setIsRefresh(true)
          
          // Pre-fill with existing data
          if (profileData.full_name) {
            setUserName(profileData.full_name)
          }
          // Try to get LinkedIn URL from interview_responses if available
          if (profileData.interview_responses?.linkedin_url) {
            setLinkedinUrl(profileData.interview_responses.linkedin_url)
          }
        }
      }
    } catch (error) {
      console.error('Error checking profile:', error)
    } finally {
      setCheckingProfile(false)
    }
  }

  const isValidLinkedInUrl = (url: string): boolean => {
    const pattern = /^https?:\/\/(www\.|[a-z]{2}\.)?linkedin\.com\/in\/[\w-]+\/?$/i
    return pattern.test(url.trim())
  }

  const handleStartMagic = async () => {
    if (!linkedinUrl.trim()) {
      toast({
        title: 'LinkedIn URL required',
        description: 'Please enter your LinkedIn profile URL to continue.',
        variant: 'destructive'
      })
      return
    }

    if (!isValidLinkedInUrl(linkedinUrl)) {
      toast({
        title: 'Invalid LinkedIn URL',
        description: 'Please enter a valid LinkedIn profile URL (e.g., https://linkedin.com/in/yourname)',
        variant: 'destructive'
      })
      return
    }

    setStep('generating')
    setLoading(true)

    try {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) {
        router.push('/login')
        return
      }

      // Step 1: Start the magic onboarding (async)
      const startResponse = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/v1/profile/sales/magic/start`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${session.access_token}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            linkedin_url: linkedinUrl.trim(),
            user_name: userName.trim() || undefined,
            company_name: companyName.trim() || undefined
          })
        }
      )

      if (!startResponse.ok) {
        const error = await startResponse.json()
        throw new Error(error.detail || 'Failed to start profile generation')
      }

      const startResult: MagicStartResponse = await startResponse.json()
      const sessionId = startResult.session_id

      // Step 2: Poll for completion
      const pollInterval = 2000 // 2 seconds
      const maxAttempts = 60 // 2 minutes max
      let attempts = 0

      const pollStatus = async (): Promise<MagicStatusResponse> => {
        const statusResponse = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL}/api/v1/profile/sales/magic/status/${sessionId}`,
          {
            headers: {
              'Authorization': `Bearer ${session.access_token}`
            }
          }
        )

        if (!statusResponse.ok) {
          throw new Error('Failed to check status')
        }

        return statusResponse.json()
      }

      // Poll until completed or failed
      while (attempts < maxAttempts) {
        const statusResult = await pollStatus()

        if (statusResult.status === 'completed') {
          // Success! Transform to MagicResult format
          const result: MagicResult = {
            success: true,
            profile_data: statusResult.profile_data || {},
            field_sources: statusResult.field_sources || {},
            missing_fields: statusResult.missing_fields || [],
            linkedin_data: statusResult.linkedin_data || {}
          }
          setMagicResult(result)
          setEditedProfile(result.profile_data)
          setStep('review')
          return
        }

        if (statusResult.status === 'failed') {
          throw new Error(statusResult.error || 'Profile generation failed')
        }

        // Still processing, wait and try again
        attempts++
        await new Promise(resolve => setTimeout(resolve, pollInterval))
      }

      // Timeout
      throw new Error('Profile generation timed out. Please try again.')

    } catch (error) {
      console.error('Magic generation failed:', error)
      toast({
        title: 'Generation Failed',
        description: error instanceof Error ? error.message : 'Could not generate profile. Please try again.',
        variant: 'destructive'
      })
      setStep('input')
    } finally {
      setLoading(false)
    }
  }

  const handleSaveProfile = async () => {
    setStep('saving')
    setLoading(true)

    try {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) {
        router.push('/login')
        return
      }

      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/v1/profile/sales/magic/confirm`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${session.access_token}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            profile_data: editedProfile,
            linkedin_url: linkedinUrl
          })
        }
      )

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Failed to save profile')
      }

      setStep('complete')
      
      toast({
        title: 'Profile Created!',
        description: 'Your sales profile has been saved successfully.'
      })

      // Redirect after short delay
      setTimeout(() => {
        router.push('/dashboard?onboarding=complete')
      }, 2000)

    } catch (error) {
      console.error('Save failed:', error)
      toast({
        title: 'Save Failed',
        description: error instanceof Error ? error.message : 'Could not save profile. Please try again.',
        variant: 'destructive'
      })
      setStep('review')
    } finally {
      setLoading(false)
    }
  }

  const updateProfileField = (field: string, value: any) => {
    setEditedProfile(prev => ({ ...prev, [field]: value }))
  }

  const toggleSection = (section: string) => {
    setExpandedSections(prev => {
      const next = new Set(prev)
      if (next.has(section)) {
        next.delete(section)
      } else {
        next.add(section)
      }
      return next
    })
  }

  const getConfidenceBadge = (field: string) => {
    const source = magicResult?.field_sources[field]
    if (!source) return null

    if (source.confidence >= 0.8) {
      return <Badge variant="default" className="bg-green-600 text-xs">From LinkedIn</Badge>
    } else if (source.confidence >= 0.5) {
      return <Badge variant="secondary" className="bg-blue-600 text-white text-xs">AI Derived</Badge>
    } else {
      return <Badge variant="outline" className="text-xs">Needs Review</Badge>
    }
  }

  // Step 1: Input LinkedIn URL
  // Show loading while checking for existing profile
  if (checkingProfile) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-violet-50 via-purple-50 to-fuchsia-50 dark:from-gray-900 dark:via-purple-900/20 dark:to-gray-900 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin mx-auto text-violet-600 mb-4" />
          <p className="text-muted-foreground">Loading your profile...</p>
        </div>
      </div>
    )
  }

  if (step === 'input') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-violet-50 via-purple-50 to-fuchsia-50 dark:from-gray-900 dark:via-purple-900/20 dark:to-gray-900 py-8 px-4">
        <div className="absolute top-4 right-4">
          <LanguageSelector currentLocale={locale} />
        </div>

        <div className="max-w-xl mx-auto">
          <Button 
            variant="ghost" 
            onClick={() => router.push(isRefresh ? '/settings/profile' : '/dashboard')}
            className="mb-6"
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            {isRefresh ? 'Back to Profile' : 'Back'}
          </Button>

          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-gradient-to-br from-violet-500 to-fuchsia-500 mb-4">
              <Wand2 className="h-8 w-8 text-white" />
            </div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-violet-600 to-fuchsia-600 bg-clip-text text-transparent">
              {isRefresh ? 'Refresh Your Profile' : 'Magic Profile Setup'}
            </h1>
            <p className="text-muted-foreground mt-2 max-w-md mx-auto">
              {isRefresh 
                ? 'Update your profile with the latest information from LinkedIn. Your existing data will be enhanced.'
                : 'Just paste your LinkedIn URL and we\'ll create your complete sales profile in seconds.'
              }
            </p>
            {isRefresh && existingProfile && (
              <div className="mt-4 inline-flex items-center gap-2 px-3 py-1.5 bg-green-100 text-green-800 rounded-full text-sm">
                <CheckCircle2 className="h-4 w-4" />
                Current profile: {existingProfile.profile_completeness || 0}% complete
              </div>
            )}
          </div>

          <Card className="shadow-xl border-0 bg-white/80 backdrop-blur">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Linkedin className="h-5 w-5 text-[#0A66C2]" />
                Your LinkedIn Profile
              </CardTitle>
              <CardDescription>
                {isRefresh 
                  ? 'We\'ll fetch the latest info from your LinkedIn profile'
                  : 'We\'ll extract your professional information automatically'
                }
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="linkedin">LinkedIn Profile URL *</Label>
                <Input
                  id="linkedin"
                  placeholder="https://linkedin.com/in/yourname"
                  value={linkedinUrl}
                  onChange={(e) => setLinkedinUrl(e.target.value)}
                  className="font-mono text-sm"
                />
                <p className="text-xs text-muted-foreground">
                  Find your profile URL by visiting LinkedIn and copying from the address bar
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="name">Full Name (optional)</Label>
                <Input
                  id="name"
                  placeholder="Your full name"
                  value={userName}
                  onChange={(e) => setUserName(e.target.value)}
                />
                <p className="text-xs text-muted-foreground">
                  Helps us identify the right profile
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="company">Current Company (optional)</Label>
                <Input
                  id="company"
                  placeholder="Your company name"
                  value={companyName}
                  onChange={(e) => setCompanyName(e.target.value)}
                />
              </div>
            </CardContent>
            <CardFooter className="flex flex-col gap-4">
              <Button 
                onClick={handleStartMagic}
                disabled={!linkedinUrl.trim()}
                className="w-full bg-gradient-to-r from-violet-600 to-fuchsia-600 hover:from-violet-700 hover:to-fuchsia-700"
                size="lg"
              >
                <Sparkles className="h-4 w-4 mr-2" />
                Generate My Profile
              </Button>
              
              <div className="text-center">
                <button 
                  onClick={() => router.push('/onboarding')}
                  className="text-sm text-muted-foreground hover:text-foreground underline"
                >
                  Or use the traditional interview instead
                </button>
              </div>
            </CardFooter>
          </Card>

          <div className="mt-8 grid grid-cols-3 gap-4 text-center">
            <div className="space-y-2">
              <div className="w-10 h-10 rounded-full bg-violet-100 flex items-center justify-center mx-auto">
                <Linkedin className="h-5 w-5 text-violet-600" />
              </div>
              <p className="text-xs text-muted-foreground">Extract from LinkedIn</p>
            </div>
            <div className="space-y-2">
              <div className="w-10 h-10 rounded-full bg-fuchsia-100 flex items-center justify-center mx-auto">
                <Sparkles className="h-5 w-5 text-fuchsia-600" />
              </div>
              <p className="text-xs text-muted-foreground">AI Enhancement</p>
            </div>
            <div className="space-y-2">
              <div className="w-10 h-10 rounded-full bg-purple-100 flex items-center justify-center mx-auto">
                <CheckCircle2 className="h-5 w-5 text-purple-600" />
              </div>
              <p className="text-xs text-muted-foreground">Review & Confirm</p>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // Step 2: Generating
  if (step === 'generating') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-violet-50 via-purple-50 to-fuchsia-50 dark:from-gray-900 dark:via-purple-900/20 dark:to-gray-900 flex items-center justify-center">
        <div className="text-center max-w-md px-4">
          <div className="relative">
            <div className="w-24 h-24 rounded-full bg-gradient-to-br from-violet-500 to-fuchsia-500 flex items-center justify-center mx-auto mb-6 animate-pulse">
              <Wand2 className="h-12 w-12 text-white" />
            </div>
            <div className="absolute -top-2 -right-2 w-8 h-8">
              <Sparkles className="h-8 w-8 text-yellow-500 animate-bounce" />
            </div>
          </div>
          <h2 className="text-2xl font-bold mb-2">Creating Your Profile</h2>
          <p className="text-muted-foreground mb-6">
            We're analyzing your LinkedIn profile and crafting a personalized sales profile...
          </p>
          <div className="space-y-3">
            <div className="flex items-center gap-3 text-sm">
              <Loader2 className="h-4 w-4 animate-spin text-violet-600" />
              <span>Fetching LinkedIn data...</span>
            </div>
            <div className="flex items-center gap-3 text-sm text-muted-foreground">
              <div className="h-4 w-4" />
              <span>Analyzing experience & skills...</span>
            </div>
            <div className="flex items-center gap-3 text-sm text-muted-foreground">
              <div className="h-4 w-4" />
              <span>Generating sales narrative...</span>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // Step 3: Review
  if (step === 'review' && magicResult) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-violet-50 via-purple-50 to-fuchsia-50 dark:from-gray-900 dark:via-purple-900/20 dark:to-gray-900 py-8 px-4">
        <div className="absolute top-4 right-4">
          <LanguageSelector currentLocale={locale} />
        </div>

        <div className="max-w-3xl mx-auto">
          <Button 
            variant="ghost" 
            onClick={() => setStep('input')}
            className="mb-6"
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Start Over
          </Button>

          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-gradient-to-br from-green-500 to-emerald-500 mb-4">
              <CheckCircle2 className="h-8 w-8 text-white" />
            </div>
            <h1 className="text-3xl font-bold">Review Your Profile</h1>
            <p className="text-muted-foreground mt-2">
              We've created your profile. Review and edit anything before saving.
            </p>
          </div>

          {/* Missing fields warning */}
          {magicResult.missing_fields.length > 0 && (
            <Card className="mb-6 border-amber-200 bg-amber-50">
              <CardContent className="pt-4">
                <div className="flex items-start gap-3">
                  <AlertCircle className="h-5 w-5 text-amber-600 mt-0.5" />
                  <div>
                    <p className="font-medium text-amber-900">Some fields need your input</p>
                    <p className="text-sm text-amber-700 mt-1">
                      These couldn't be determined from your LinkedIn: {magicResult.missing_fields.join(', ')}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Identity Section */}
          <Card className="mb-4 shadow-lg border-0 bg-white/80 backdrop-blur overflow-hidden">
            <button
              onClick={() => toggleSection('identity')}
              className="w-full px-6 py-4 flex items-center justify-between hover:bg-muted/50 transition-colors"
            >
              <div className="flex items-center gap-3">
                <User className="h-5 w-5 text-violet-600" />
                <span className="font-semibold">Identity & Background</span>
              </div>
              <ArrowRight className={`h-4 w-4 transition-transform ${expandedSections.has('identity') ? 'rotate-90' : ''}`} />
            </button>
            
            {expandedSections.has('identity') && (
              <CardContent className="border-t pt-4 space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Label>Full Name</Label>
                      {getConfidenceBadge('full_name')}
                    </div>
                    <Input
                      value={editedProfile.full_name || ''}
                      onChange={(e) => updateProfileField('full_name', e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Label>Role</Label>
                      {getConfidenceBadge('role')}
                    </div>
                    <Input
                      value={editedProfile.role || ''}
                      onChange={(e) => updateProfileField('role', e.target.value)}
                    />
                  </div>
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Label>Years of Experience</Label>
                      {getConfidenceBadge('experience_years')}
                    </div>
                    <Input
                      type="number"
                      value={editedProfile.experience_years || ''}
                      onChange={(e) => updateProfileField('experience_years', parseInt(e.target.value) || null)}
                    />
                  </div>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Label>Communication Style</Label>
                      {getConfidenceBadge('communication_style')}
                    </div>
                    <Input
                      value={editedProfile.communication_style || ''}
                      onChange={(e) => updateProfileField('communication_style', e.target.value)}
                      placeholder="e.g., Direct, Consultative, Relationship-focused"
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label>Strengths</Label>
                    {getConfidenceBadge('strengths')}
                  </div>
                  <Input
                    value={Array.isArray(editedProfile.strengths) ? editedProfile.strengths.join(', ') : ''}
                    onChange={(e) => updateProfileField('strengths', e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
                    placeholder="Comma-separated list of strengths"
                  />
                </div>
              </CardContent>
            )}
          </Card>

          {/* Sales Approach Section */}
          <Card className="mb-4 shadow-lg border-0 bg-white/80 backdrop-blur overflow-hidden">
            <button
              onClick={() => toggleSection('approach')}
              className="w-full px-6 py-4 flex items-center justify-between hover:bg-muted/50 transition-colors"
            >
              <div className="flex items-center gap-3">
                <Briefcase className="h-5 w-5 text-fuchsia-600" />
                <span className="font-semibold">Sales Approach</span>
              </div>
              <ArrowRight className={`h-4 w-4 transition-transform ${expandedSections.has('approach') ? 'rotate-90' : ''}`} />
            </button>
            
            {expandedSections.has('approach') && (
              <CardContent className="border-t pt-4 space-y-4">
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label>Sales Methodology</Label>
                    {getConfidenceBadge('sales_methodology')}
                  </div>
                  <Input
                    value={editedProfile.sales_methodology || ''}
                    onChange={(e) => updateProfileField('sales_methodology', e.target.value)}
                    placeholder="e.g., SPIN Selling, Challenger, Consultative"
                  />
                </div>

                <div className="space-y-2">
                  <Label>Methodology Description</Label>
                  <Textarea
                    value={editedProfile.methodology_description || ''}
                    onChange={(e) => updateProfileField('methodology_description', e.target.value)}
                    placeholder="Describe your sales approach..."
                    rows={3}
                  />
                </div>

                <div className="space-y-2">
                  <Label>Preferred Meeting Types</Label>
                  <Input
                    value={Array.isArray(editedProfile.preferred_meeting_types) ? editedProfile.preferred_meeting_types.join(', ') : ''}
                    onChange={(e) => updateProfileField('preferred_meeting_types', e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
                    placeholder="e.g., discovery, demo, closing"
                  />
                </div>
              </CardContent>
            )}
          </Card>

          {/* Target Market Section */}
          <Card className="mb-4 shadow-lg border-0 bg-white/80 backdrop-blur overflow-hidden">
            <button
              onClick={() => toggleSection('target')}
              className="w-full px-6 py-4 flex items-center justify-between hover:bg-muted/50 transition-colors"
            >
              <div className="flex items-center gap-3">
                <Target className="h-5 w-5 text-purple-600" />
                <span className="font-semibold">Target Market</span>
              </div>
              <ArrowRight className={`h-4 w-4 transition-transform ${expandedSections.has('target') ? 'rotate-90' : ''}`} />
            </button>
            
            {expandedSections.has('target') && (
              <CardContent className="border-t pt-4 space-y-4">
                <div className="space-y-2">
                  <Label>Target Industries</Label>
                  <Input
                    value={Array.isArray(editedProfile.target_industries) ? editedProfile.target_industries.join(', ') : ''}
                    onChange={(e) => updateProfileField('target_industries', e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
                    placeholder="e.g., SaaS, FinTech, Healthcare"
                  />
                </div>

                <div className="space-y-2">
                  <Label>Target Regions</Label>
                  <Input
                    value={Array.isArray(editedProfile.target_regions) ? editedProfile.target_regions.join(', ') : ''}
                    onChange={(e) => updateProfileField('target_regions', e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
                    placeholder="e.g., Benelux, DACH, North America"
                  />
                </div>

                <div className="space-y-2">
                  <Label>Target Company Sizes</Label>
                  <Input
                    value={Array.isArray(editedProfile.target_company_sizes) ? editedProfile.target_company_sizes.join(', ') : ''}
                    onChange={(e) => updateProfileField('target_company_sizes', e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
                    placeholder="e.g., 50-200, 200-1000, 1000+"
                  />
                </div>

                <div className="space-y-2">
                  <Label>Quarterly Goals</Label>
                  <Textarea
                    value={editedProfile.quarterly_goals || ''}
                    onChange={(e) => updateProfileField('quarterly_goals', e.target.value)}
                    placeholder="What are you working towards this quarter?"
                    rows={2}
                  />
                </div>
              </CardContent>
            )}
          </Card>

          {/* Communication Style Section */}
          <Card className="mb-4 shadow-lg border-0 bg-white/80 backdrop-blur overflow-hidden">
            <button
              onClick={() => toggleSection('communication')}
              className="w-full px-6 py-4 flex items-center justify-between hover:bg-muted/50 transition-colors"
            >
              <div className="flex items-center gap-3">
                <MessageSquare className="h-5 w-5 text-emerald-600" />
                <span className="font-semibold">Communication Preferences</span>
              </div>
              <ArrowRight className={`h-4 w-4 transition-transform ${expandedSections.has('communication') ? 'rotate-90' : ''}`} />
            </button>
            
            {expandedSections.has('communication') && (
              <CardContent className="border-t pt-4 space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Email Tone</Label>
                    <Input
                      value={editedProfile.email_tone || ''}
                      onChange={(e) => updateProfileField('email_tone', e.target.value)}
                      placeholder="e.g., direct, warm, formal, casual"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Email Sign-off</Label>
                    <Input
                      value={editedProfile.email_signoff || ''}
                      onChange={(e) => updateProfileField('email_signoff', e.target.value)}
                      placeholder="e.g., Best regards, Cheers"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Writing Length</Label>
                    <Input
                      value={editedProfile.writing_length_preference || ''}
                      onChange={(e) => updateProfileField('writing_length_preference', e.target.value)}
                      placeholder="concise or detailed"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Use Emojis?</Label>
                    <div className="flex items-center gap-4 h-10">
                      <label className="flex items-center gap-2">
                        <input
                          type="radio"
                          name="emoji"
                          checked={editedProfile.uses_emoji === true}
                          onChange={() => updateProfileField('uses_emoji', true)}
                        />
                        Yes
                      </label>
                      <label className="flex items-center gap-2">
                        <input
                          type="radio"
                          name="emoji"
                          checked={editedProfile.uses_emoji === false}
                          onChange={() => updateProfileField('uses_emoji', false)}
                        />
                        No
                      </label>
                    </div>
                  </div>
                </div>
              </CardContent>
            )}
          </Card>

          {/* AI Summary Section */}
          <Card className="mb-6 shadow-lg border-0 bg-white/80 backdrop-blur overflow-hidden">
            <button
              onClick={() => toggleSection('summary')}
              className="w-full px-6 py-4 flex items-center justify-between hover:bg-muted/50 transition-colors"
            >
              <div className="flex items-center gap-3">
                <Edit3 className="h-5 w-5 text-amber-600" />
                <span className="font-semibold">AI Generated Summary</span>
              </div>
              <ArrowRight className={`h-4 w-4 transition-transform ${expandedSections.has('summary') ? 'rotate-90' : ''}`} />
            </button>
            
            {expandedSections.has('summary') && (
              <CardContent className="border-t pt-4 space-y-4">
                <div className="space-y-2">
                  <Label>Brief Summary</Label>
                  <Textarea
                    value={editedProfile.ai_summary || ''}
                    onChange={(e) => updateProfileField('ai_summary', e.target.value)}
                    rows={3}
                  />
                </div>

                <div className="space-y-2">
                  <Label>Full Narrative</Label>
                  <Textarea
                    value={editedProfile.sales_narrative || ''}
                    onChange={(e) => updateProfileField('sales_narrative', e.target.value)}
                    rows={8}
                  />
                </div>
              </CardContent>
            )}
          </Card>

          {/* Action Buttons */}
          <div className="flex gap-4">
            <Button
              variant="outline"
              onClick={() => setStep('input')}
              className="flex-1"
            >
              <ArrowLeft className="h-4 w-4 mr-2" />
              Start Over
            </Button>
            <Button
              onClick={handleSaveProfile}
              className="flex-1 bg-gradient-to-r from-violet-600 to-fuchsia-600 hover:from-violet-700 hover:to-fuchsia-700"
            >
              <CheckCircle2 className="h-4 w-4 mr-2" />
              Save Profile
            </Button>
          </div>
        </div>
      </div>
    )
  }

  // Step 4: Saving
  if (step === 'saving') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-violet-50 via-purple-50 to-fuchsia-50 dark:from-gray-900 dark:via-purple-900/20 dark:to-gray-900 flex items-center justify-center">
        <div className="text-center max-w-md px-4">
          <Loader2 className="h-12 w-12 animate-spin text-violet-600 mx-auto mb-6" />
          <h2 className="text-2xl font-bold mb-2">Saving Your Profile</h2>
          <p className="text-muted-foreground">Just a moment...</p>
        </div>
      </div>
    )
  }

  // Step 5: Complete
  if (step === 'complete') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-violet-50 via-purple-50 to-fuchsia-50 dark:from-gray-900 dark:via-purple-900/20 dark:to-gray-900 flex items-center justify-center">
        <div className="text-center max-w-md px-4">
          <div className="w-24 h-24 rounded-full bg-gradient-to-br from-green-500 to-emerald-500 flex items-center justify-center mx-auto mb-6">
            <CheckCircle2 className="h-12 w-12 text-white" />
          </div>
          <h2 className="text-2xl font-bold mb-2">Profile Created!</h2>
          <p className="text-muted-foreground mb-6">
            Your sales profile is ready. DealMotion will now personalize all outputs just for you.
          </p>
          <Button 
            onClick={() => router.push('/dashboard')}
            className="bg-gradient-to-r from-violet-600 to-fuchsia-600"
          >
            Go to Dashboard
          </Button>
        </div>
      </div>
    )
  }

  return null
}

