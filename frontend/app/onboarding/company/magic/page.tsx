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
  Building2,
  Globe,
  Linkedin,
  Search,
  Target,
  Users,
  FileText,
  Wand2,
  ExternalLink
} from 'lucide-react'

type WizardStep = 'search' | 'searching' | 'select' | 'generating' | 'review' | 'saving' | 'complete'

interface CompanyOption {
  company_name: string
  description?: string
  website?: string
  linkedin_url?: string
  location?: string
  confidence?: number
}

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
  selected_company?: CompanyOption
  error?: string
}

interface MagicResult {
  success: boolean
  profile_data: Record<string, any>
  field_sources: Record<string, FieldSource>
  missing_fields: string[]
  selected_company?: CompanyOption
  error?: string
}

export default function CompanyMagicOnboardingPage() {
  const router = useRouter()
  const supabase = createClientComponentClient()
  const { toast } = useToast()
  const t = useTranslations('onboarding')
  const locale = useLocale() as Locale
  
  const [step, setStep] = useState<WizardStep>('search')
  const [companyName, setCompanyName] = useState('')
  const [country, setCountry] = useState('')
  const [loading, setLoading] = useState(false)
  const [companyOptions, setCompanyOptions] = useState<CompanyOption[]>([])
  const [selectedCompany, setSelectedCompany] = useState<CompanyOption | null>(null)
  const [magicResult, setMagicResult] = useState<MagicResult | null>(null)
  const [editedProfile, setEditedProfile] = useState<Record<string, any>>({})
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['basics', 'value']))
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

      // Check if organization already has a company profile
      const profileResponse = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/v1/profile/company`,
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
          if (profileData.company_name) {
            setCompanyName(profileData.company_name)
          }
        }
      }
    } catch (error) {
      console.error('Error checking profile:', error)
    } finally {
      setCheckingProfile(false)
    }
  }

  const handleSearchCompany = async () => {
    if (!companyName.trim() || !country.trim()) {
      toast({
        title: 'Missing Information',
        description: 'Please enter both company name and country.',
        variant: 'destructive'
      })
      return
    }

    setStep('searching')
    setLoading(true)

    try {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) {
        router.push('/login')
        return
      }

      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/v1/profile/company/magic/search`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${session.access_token}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            company_name: companyName.trim(),
            country: country.trim()
          })
        }
      )

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Failed to search company')
      }

      const result = await response.json()
      
      if (result.company_options && result.company_options.length > 0) {
        setCompanyOptions(result.company_options)
        setStep('select')
      } else {
        // No options found, allow manual entry
        setCompanyOptions([{
          company_name: companyName,
          location: country,
          description: 'No matches found - proceed with manual entry'
        }])
        setStep('select')
      }

    } catch (error) {
      console.error('Company search failed:', error)
      toast({
        title: 'Search Failed',
        description: error instanceof Error ? error.message : 'Could not search for company.',
        variant: 'destructive'
      })
      setStep('search')
    } finally {
      setLoading(false)
    }
  }

  const handleSelectCompany = async (company: CompanyOption) => {
    setSelectedCompany(company)
    setStep('generating')
    setLoading(true)

    try {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) {
        router.push('/login')
        return
      }

      // Step 1: Start the company profile generation (async)
      const startResponse = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/v1/profile/company/magic/generate`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${session.access_token}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            company_name: company.company_name,
            website: company.website || undefined,
            linkedin_url: company.linkedin_url || undefined,
            country: company.location || country
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
          `${process.env.NEXT_PUBLIC_API_URL}/api/v1/profile/company/magic/status/${sessionId}`,
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
            selected_company: statusResult.selected_company
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
      console.error('Profile generation failed:', error)
      toast({
        title: 'Generation Failed',
        description: error instanceof Error ? error.message : 'Could not generate profile.',
        variant: 'destructive'
      })
      setStep('select')
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
        `${process.env.NEXT_PUBLIC_API_URL}/api/v1/profile/company/magic/confirm`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${session.access_token}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            profile_data: editedProfile
          })
        }
      )

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Failed to save profile')
      }

      setStep('complete')
      
      toast({
        title: 'Company Profile Created!',
        description: 'Your company profile has been saved successfully.'
      })

      setTimeout(() => {
        router.push('/dashboard/company-profile')
      }, 2000)

    } catch (error) {
      console.error('Save failed:', error)
      toast({
        title: 'Save Failed',
        description: error instanceof Error ? error.message : 'Could not save profile.',
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

  const updateNestedField = (parent: string, field: string, value: any) => {
    setEditedProfile(prev => ({
      ...prev,
      [parent]: {
        ...(prev[parent] || {}),
        [field]: value
      }
    }))
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
      return <Badge variant="default" className="bg-green-600 text-xs">Known</Badge>
    } else if (source.confidence >= 0.5) {
      return <Badge variant="secondary" className="bg-blue-600 text-white text-xs">AI Derived</Badge>
    } else {
      return <Badge variant="outline" className="text-xs">Needs Review</Badge>
    }
  }

  // Step 1: Search for company
  // Show loading while checking for existing profile
  if (checkingProfile) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 dark:from-gray-900 dark:via-indigo-900/20 dark:to-gray-900 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin mx-auto text-blue-600 mb-4" />
          <p className="text-muted-foreground">Loading your company profile...</p>
        </div>
      </div>
    )
  }

  if (step === 'search') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 dark:from-gray-900 dark:via-indigo-900/20 dark:to-gray-900 py-8 px-4">
        <div className="absolute top-4 right-4">
          <LanguageSelector currentLocale={locale} />
        </div>

        <div className="max-w-xl mx-auto">
          <Button 
            variant="ghost" 
            onClick={() => router.push(isRefresh ? '/settings/company' : '/dashboard')}
            className="mb-6"
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            {isRefresh ? 'Back to Company Profile' : 'Back'}
          </Button>

          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-gradient-to-br from-blue-500 to-indigo-500 mb-4">
              <Building2 className="h-8 w-8 text-white" />
            </div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
              {isRefresh ? 'Refresh Company Profile' : 'Magic Company Setup'}
            </h1>
            <p className="text-muted-foreground mt-2 max-w-md mx-auto">
              {isRefresh
                ? 'Update your company profile with the latest information. Your existing data will be enhanced.'
                : 'Enter your company name and we\'ll create a comprehensive company profile automatically.'
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
                <Search className="h-5 w-5 text-blue-600" />
                {isRefresh ? 'Update Your Company' : 'Find Your Company'}
              </CardTitle>
              <CardDescription>
                {isRefresh
                  ? 'We\'ll fetch the latest information about your company'
                  : 'We\'ll search for your company and gather information automatically'
                }
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="company">Company Name *</Label>
                <Input
                  id="company"
                  placeholder="e.g., Acme Corporation"
                  value={companyName}
                  onChange={(e) => setCompanyName(e.target.value)}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="country">Country *</Label>
                <Input
                  id="country"
                  placeholder="e.g., Netherlands, Germany, USA"
                  value={country}
                  onChange={(e) => setCountry(e.target.value)}
                />
                <p className="text-xs text-muted-foreground">
                  Helps us find the correct company
                </p>
              </div>
            </CardContent>
            <CardFooter className="flex flex-col gap-4">
              <Button 
                onClick={handleSearchCompany}
                disabled={!companyName.trim() || !country.trim()}
                className="w-full bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700"
                size="lg"
              >
                <Search className="h-4 w-4 mr-2" />
                Find Company
              </Button>
              
              <div className="text-center">
                <button 
                  onClick={() => router.push('/onboarding/company')}
                  className="text-sm text-muted-foreground hover:text-foreground underline"
                >
                  Or use the traditional interview instead
                </button>
              </div>
            </CardFooter>
          </Card>

          <div className="mt-8 grid grid-cols-3 gap-4 text-center">
            <div className="space-y-2">
              <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center mx-auto">
                <Search className="h-5 w-5 text-blue-600" />
              </div>
              <p className="text-xs text-muted-foreground">Find Company</p>
            </div>
            <div className="space-y-2">
              <div className="w-10 h-10 rounded-full bg-indigo-100 flex items-center justify-center mx-auto">
                <Wand2 className="h-5 w-5 text-indigo-600" />
              </div>
              <p className="text-xs text-muted-foreground">AI Research</p>
            </div>
            <div className="space-y-2">
              <div className="w-10 h-10 rounded-full bg-purple-100 flex items-center justify-center mx-auto">
                <CheckCircle2 className="h-5 w-5 text-purple-600" />
              </div>
              <p className="text-xs text-muted-foreground">Review & Save</p>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // Step 2: Searching
  if (step === 'searching') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 flex items-center justify-center">
        <div className="text-center max-w-md px-4">
          <Loader2 className="h-12 w-12 animate-spin text-blue-600 mx-auto mb-6" />
          <h2 className="text-2xl font-bold mb-2">Searching for Company</h2>
          <p className="text-muted-foreground">
            Looking for "{companyName}" in {country}...
          </p>
        </div>
      </div>
    )
  }

  // Step 3: Select company
  if (step === 'select') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 py-8 px-4">
        <div className="max-w-2xl mx-auto">
          <Button 
            variant="ghost" 
            onClick={() => setStep('search')}
            className="mb-6"
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Search
          </Button>

          <div className="text-center mb-8">
            <h1 className="text-2xl font-bold">Select Your Company</h1>
            <p className="text-muted-foreground mt-2">
              We found {companyOptions.length} option{companyOptions.length !== 1 ? 's' : ''} for "{companyName}"
            </p>
          </div>

          <div className="space-y-4">
            {companyOptions.map((company, index) => (
              <Card 
                key={index}
                className="shadow-lg border-0 bg-white/80 backdrop-blur cursor-pointer hover:shadow-xl transition-shadow"
                onClick={() => handleSelectCompany(company)}
              >
                <CardContent className="pt-6">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <h3 className="font-semibold text-lg">{company.company_name}</h3>
                      {company.description && (
                        <p className="text-sm text-muted-foreground mt-1">{company.description}</p>
                      )}
                      <div className="flex items-center gap-4 mt-3 text-sm">
                        {company.location && (
                          <span className="flex items-center gap-1 text-muted-foreground">
                            <Globe className="h-3 w-3" />
                            {company.location}
                          </span>
                        )}
                        {company.website && (
                          <a 
                            href={company.website}
                            target="_blank"
                            rel="noopener noreferrer"
                            onClick={(e) => e.stopPropagation()}
                            className="flex items-center gap-1 text-blue-600 hover:underline"
                          >
                            <ExternalLink className="h-3 w-3" />
                            Website
                          </a>
                        )}
                        {company.linkedin_url && (
                          <a 
                            href={company.linkedin_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            onClick={(e) => e.stopPropagation()}
                            className="flex items-center gap-1 text-[#0A66C2] hover:underline"
                          >
                            <Linkedin className="h-3 w-3" />
                            LinkedIn
                          </a>
                        )}
                      </div>
                    </div>
                    <Button variant="ghost" size="sm">
                      <ArrowRight className="h-4 w-4" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          <div className="mt-6 text-center">
            <button
              onClick={() => handleSelectCompany({
                company_name: companyName,
                location: country
              })}
              className="text-sm text-muted-foreground hover:text-foreground underline"
            >
              Company not listed? Proceed with "{companyName}" anyway
            </button>
          </div>
        </div>
      </div>
    )
  }

  // Step 4: Generating
  if (step === 'generating') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 flex items-center justify-center">
        <div className="text-center max-w-md px-4">
          <div className="relative">
            <div className="w-24 h-24 rounded-full bg-gradient-to-br from-blue-500 to-indigo-500 flex items-center justify-center mx-auto mb-6 animate-pulse">
              <Wand2 className="h-12 w-12 text-white" />
            </div>
            <div className="absolute -top-2 -right-2 w-8 h-8">
              <Sparkles className="h-8 w-8 text-yellow-500 animate-bounce" />
            </div>
          </div>
          <h2 className="text-2xl font-bold mb-2">Creating Company Profile</h2>
          <p className="text-muted-foreground mb-6">
            Researching {selectedCompany?.company_name}...
          </p>
          <div className="space-y-3">
            <div className="flex items-center gap-3 text-sm">
              <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
              <span>Analyzing company information...</span>
            </div>
            <div className="flex items-center gap-3 text-sm text-muted-foreground">
              <div className="h-4 w-4" />
              <span>Identifying products & value props...</span>
            </div>
            <div className="flex items-center gap-3 text-sm text-muted-foreground">
              <div className="h-4 w-4" />
              <span>Generating company narrative...</span>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // Step 5: Review
  if (step === 'review' && magicResult) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 py-8 px-4">
        <div className="absolute top-4 right-4">
          <LanguageSelector currentLocale={locale} />
        </div>

        <div className="max-w-3xl mx-auto">
          <Button 
            variant="ghost" 
            onClick={() => setStep('search')}
            className="mb-6"
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Start Over
          </Button>

          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-gradient-to-br from-green-500 to-emerald-500 mb-4">
              <CheckCircle2 className="h-8 w-8 text-white" />
            </div>
            <h1 className="text-3xl font-bold">Review Company Profile</h1>
            <p className="text-muted-foreground mt-2">
              We've created your company profile. Review and edit before saving.
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
                      These couldn't be determined: {magicResult.missing_fields.join(', ')}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Company Basics Section */}
          <Card className="mb-4 shadow-lg border-0 bg-white/80 backdrop-blur overflow-hidden">
            <button
              onClick={() => toggleSection('basics')}
              className="w-full px-6 py-4 flex items-center justify-between hover:bg-muted/50 transition-colors"
            >
              <div className="flex items-center gap-3">
                <Building2 className="h-5 w-5 text-blue-600" />
                <span className="font-semibold">Company Basics</span>
              </div>
              <ArrowRight className={`h-4 w-4 transition-transform ${expandedSections.has('basics') ? 'rotate-90' : ''}`} />
            </button>
            
            {expandedSections.has('basics') && (
              <CardContent className="border-t pt-4 space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Label>Company Name</Label>
                      {getConfidenceBadge('company_name')}
                    </div>
                    <Input
                      value={editedProfile.company_name || ''}
                      onChange={(e) => updateProfileField('company_name', e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Label>Industry</Label>
                      {getConfidenceBadge('industry')}
                    </div>
                    <Input
                      value={editedProfile.industry || ''}
                      onChange={(e) => updateProfileField('industry', e.target.value)}
                    />
                  </div>
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Website</Label>
                    <Input
                      value={editedProfile.website || ''}
                      onChange={(e) => updateProfileField('website', e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Company Size</Label>
                    <Input
                      value={editedProfile.company_size || ''}
                      onChange={(e) => updateProfileField('company_size', e.target.value)}
                      placeholder="e.g., 50-200 employees"
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label>Headquarters</Label>
                  <Input
                    value={editedProfile.headquarters || ''}
                    onChange={(e) => updateProfileField('headquarters', e.target.value)}
                  />
                </div>
              </CardContent>
            )}
          </Card>

          {/* Value & Products Section */}
          <Card className="mb-4 shadow-lg border-0 bg-white/80 backdrop-blur overflow-hidden">
            <button
              onClick={() => toggleSection('value')}
              className="w-full px-6 py-4 flex items-center justify-between hover:bg-muted/50 transition-colors"
            >
              <div className="flex items-center gap-3">
                <Sparkles className="h-5 w-5 text-indigo-600" />
                <span className="font-semibold">Value & Differentiation</span>
              </div>
              <ArrowRight className={`h-4 w-4 transition-transform ${expandedSections.has('value') ? 'rotate-90' : ''}`} />
            </button>
            
            {expandedSections.has('value') && (
              <CardContent className="border-t pt-4 space-y-4">
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label>Core Value Propositions</Label>
                    {getConfidenceBadge('core_value_props')}
                  </div>
                  <Textarea
                    value={Array.isArray(editedProfile.core_value_props) ? editedProfile.core_value_props.join('\n') : ''}
                    onChange={(e) => updateProfileField('core_value_props', e.target.value.split('\n').filter(Boolean))}
                    placeholder="One value proposition per line"
                    rows={4}
                  />
                </div>

                <div className="space-y-2">
                  <Label>Key Differentiators</Label>
                  <Textarea
                    value={Array.isArray(editedProfile.differentiators) ? editedProfile.differentiators.join('\n') : ''}
                    onChange={(e) => updateProfileField('differentiators', e.target.value.split('\n').filter(Boolean))}
                    placeholder="One differentiator per line"
                    rows={3}
                  />
                </div>

                <div className="space-y-2">
                  <Label>Unique Selling Points</Label>
                  <Textarea
                    value={editedProfile.unique_selling_points || ''}
                    onChange={(e) => updateProfileField('unique_selling_points', e.target.value)}
                    rows={3}
                  />
                </div>

                <div className="space-y-2">
                  <Label>Competitive Advantages</Label>
                  <Textarea
                    value={editedProfile.competitive_advantages || ''}
                    onChange={(e) => updateProfileField('competitive_advantages', e.target.value)}
                    rows={3}
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
                <span className="font-semibold">Target Market & ICP</span>
              </div>
              <ArrowRight className={`h-4 w-4 transition-transform ${expandedSections.has('target') ? 'rotate-90' : ''}`} />
            </button>
            
            {expandedSections.has('target') && (
              <CardContent className="border-t pt-4 space-y-4">
                <div className="space-y-2">
                  <Label>Target Industries</Label>
                  <Input
                    value={editedProfile.ideal_customer_profile?.industries?.join(', ') || ''}
                    onChange={(e) => updateNestedField('ideal_customer_profile', 'industries', e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
                    placeholder="Comma-separated industries"
                  />
                </div>

                <div className="space-y-2">
                  <Label>Target Company Sizes</Label>
                  <Input
                    value={editedProfile.ideal_customer_profile?.company_sizes?.join(', ') || ''}
                    onChange={(e) => updateNestedField('ideal_customer_profile', 'company_sizes', e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
                    placeholder="e.g., 50-200, 200-1000"
                  />
                </div>

                <div className="space-y-2">
                  <Label>Target Regions</Label>
                  <Input
                    value={editedProfile.ideal_customer_profile?.regions?.join(', ') || ''}
                    onChange={(e) => updateNestedField('ideal_customer_profile', 'regions', e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
                    placeholder="e.g., Europe, North America"
                  />
                </div>

                <div className="space-y-2">
                  <Label>Pain Points You Solve</Label>
                  <Textarea
                    value={editedProfile.ideal_customer_profile?.pain_points?.join('\n') || ''}
                    onChange={(e) => updateNestedField('ideal_customer_profile', 'pain_points', e.target.value.split('\n').filter(Boolean))}
                    placeholder="One pain point per line"
                    rows={3}
                  />
                </div>
              </CardContent>
            )}
          </Card>

          {/* Business Info Section */}
          <Card className="mb-4 shadow-lg border-0 bg-white/80 backdrop-blur overflow-hidden">
            <button
              onClick={() => toggleSection('business')}
              className="w-full px-6 py-4 flex items-center justify-between hover:bg-muted/50 transition-colors"
            >
              <div className="flex items-center gap-3">
                <Users className="h-5 w-5 text-emerald-600" />
                <span className="font-semibold">Business Information</span>
              </div>
              <ArrowRight className={`h-4 w-4 transition-transform ${expandedSections.has('business') ? 'rotate-90' : ''}`} />
            </button>
            
            {expandedSections.has('business') && (
              <CardContent className="border-t pt-4 space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Typical Sales Cycle</Label>
                    <Input
                      value={editedProfile.typical_sales_cycle || ''}
                      onChange={(e) => updateProfileField('typical_sales_cycle', e.target.value)}
                      placeholder="e.g., 1-3 months"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Average Deal Size</Label>
                    <Input
                      value={editedProfile.average_deal_size || ''}
                      onChange={(e) => updateProfileField('average_deal_size', e.target.value)}
                      placeholder="e.g., €10,000 - €50,000"
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label>Main Competitors</Label>
                  <Input
                    value={Array.isArray(editedProfile.competitors) ? editedProfile.competitors.join(', ') : ''}
                    onChange={(e) => updateProfileField('competitors', e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
                    placeholder="Comma-separated competitors"
                  />
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
                <FileText className="h-5 w-5 text-amber-600" />
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
                  <Label>Company Narrative</Label>
                  <Textarea
                    value={editedProfile.company_narrative || ''}
                    onChange={(e) => updateProfileField('company_narrative', e.target.value)}
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
              onClick={() => setStep('search')}
              className="flex-1"
            >
              <ArrowLeft className="h-4 w-4 mr-2" />
              Start Over
            </Button>
            <Button
              onClick={handleSaveProfile}
              className="flex-1 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700"
            >
              <CheckCircle2 className="h-4 w-4 mr-2" />
              Save Company Profile
            </Button>
          </div>
        </div>
      </div>
    )
  }

  // Step 6: Saving
  if (step === 'saving') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 flex items-center justify-center">
        <div className="text-center max-w-md px-4">
          <Loader2 className="h-12 w-12 animate-spin text-blue-600 mx-auto mb-6" />
          <h2 className="text-2xl font-bold mb-2">Saving Company Profile</h2>
          <p className="text-muted-foreground">Just a moment...</p>
        </div>
      </div>
    )
  }

  // Step 7: Complete
  if (step === 'complete') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 flex items-center justify-center">
        <div className="text-center max-w-md px-4">
          <div className="w-24 h-24 rounded-full bg-gradient-to-br from-green-500 to-emerald-500 flex items-center justify-center mx-auto mb-6">
            <CheckCircle2 className="h-12 w-12 text-white" />
          </div>
          <h2 className="text-2xl font-bold mb-2">Company Profile Created!</h2>
          <p className="text-muted-foreground mb-6">
            Your company profile is ready. DealMotion will use this to personalize all sales content.
          </p>
          <Button 
            onClick={() => router.push('/dashboard/company-profile')}
            className="bg-gradient-to-r from-blue-600 to-indigo-600"
          >
            View Company Profile
          </Button>
        </div>
      </div>
    )
  }

  return null
}

