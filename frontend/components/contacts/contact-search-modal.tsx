'use client'

import { useState, useEffect } from 'react'
import { useTranslations } from 'next-intl'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import { Textarea } from '@/components/ui/textarea'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet'
import { Icons } from '@/components/icons'
import { ContactMatchCard, ContactMatch } from './contact-match-card'
import { useToast } from '@/components/ui/use-toast'
import { api } from '@/lib/api'

type ModalStep = 'search' | 'loading' | 'results' | 'enrich' | 'confirm'

interface ResearchExecutive {
  name: string
  title?: string
  linkedin_url?: string
  background?: string
}

interface Contact {
  id: string
  prospect_id: string
  name: string
  role?: string
  linkedin_url?: string
  email?: string
  phone?: string
  is_primary: boolean
  created_at: string
}

interface ContactSearchModalProps {
  isOpen: boolean
  onClose: () => void
  companyName: string
  companyLinkedInUrl?: string
  researchId: string
  onContactAdded: (contact: Contact) => void
}

export function ContactSearchModal({
  isOpen,
  onClose,
  companyName,
  companyLinkedInUrl,
  researchId,
  onContactAdded
}: ContactSearchModalProps) {
  const t = useTranslations('research')
  const { toast } = useToast()

  // Form state
  const [step, setStep] = useState<ModalStep>('search')
  const [searchName, setSearchName] = useState('')
  const [searchRole, setSearchRole] = useState('')
  const [matches, setMatches] = useState<ContactMatch[]>([])
  const [selectedMatch, setSelectedMatch] = useState<ContactMatch | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Research executives suggestions
  const [executives, setExecutives] = useState<ResearchExecutive[]>([])
  const [loadingExecutives, setLoadingExecutives] = useState(false)

  // Enrich step - user-provided LinkedIn info
  const [linkedinAbout, setLinkedinAbout] = useState('')
  const [linkedinExperience, setLinkedinExperience] = useState('')
  const [additionalNotes, setAdditionalNotes] = useState('')

  // Confirm step additional fields
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [isPrimary, setIsPrimary] = useState(false)
  const [isAdding, setIsAdding] = useState(false)

  // Load executives from research when modal opens
  useEffect(() => {
    if (isOpen && researchId) {
      loadExecutives()
    }
  }, [isOpen, researchId])

  const loadExecutives = async () => {
    setLoadingExecutives(true)
    try {
      const { data, error } = await api.get<{
        executives: ResearchExecutive[]
        company_name: string
      }>(`/api/v1/research/${researchId}/executives`)

      if (!error && data?.executives) {
        setExecutives(data.executives)
      }
    } catch (err) {
      // Silently fail - executives are optional suggestions
      console.log('Could not load executives:', err)
    } finally {
      setLoadingExecutives(false)
    }
  }

  // Select an executive - ALWAYS search for LinkedIn profiles
  const handleSelectExecutive = async (exec: ResearchExecutive) => {
    // Set the search fields and ALWAYS perform a LinkedIn search
    setSearchName(exec.name)
    setSearchRole(exec.title || '')
    setStep('loading')
    setError(null)

    try {
      const { data, error: searchError } = await api.post<{
        matches: ContactMatch[]
        search_query_used: string
        error?: string
      }>('/api/v1/contacts/search', {
        name: exec.name,
        role: exec.title || undefined,
        company_name: companyName,
        company_linkedin_url: companyLinkedInUrl,
        research_id: researchId
      })

      if (searchError || data?.error) {
        setError(searchError?.message || data?.error || 'Search failed')
        setStep('search')
        return
      }

      setMatches(data?.matches || [])
      setStep('results')
    } catch (err) {
      setError('Search failed. Please try again.')
      setStep('search')
    }
  }

  // Reset state when modal closes
  const handleClose = () => {
    setStep('search')
    setSearchName('')
    setSearchRole('')
    setMatches([])
    setSelectedMatch(null)
    setError(null)
    setLinkedinAbout('')
    setLinkedinExperience('')
    setAdditionalNotes('')
    setEmail('')
    setPhone('')
    setIsPrimary(false)
    // Don't reset executives - they persist for the research
    onClose()
  }

  // Search for profiles
  const handleSearch = async () => {
    if (!searchName.trim()) {
      toast({
        variant: 'destructive',
        title: t('contacts.search.nameLabel'),
        description: t('contacts.search.namePlaceholder')
      })
      return
    }

    setStep('loading')
    setError(null)

    try {
      const { data, error } = await api.post<{
        matches: ContactMatch[]
        search_query_used: string
        error?: string
      }>('/api/v1/contacts/search', {
        name: searchName.trim(),
        role: searchRole.trim() || undefined,
        company_name: companyName,
        company_linkedin_url: companyLinkedInUrl,
        research_id: researchId  // Include research_id for executive matching
      })

      if (error || data?.error) {
        setError(error?.message || data?.error || 'Search failed')
        setStep('search')
        return
      }

      setMatches(data?.matches || [])
      setStep('results')
    } catch (err) {
      setError('Search failed. Please try again.')
      setStep('search')
    }
  }

  // State for enrichment loading
  const [isEnriching, setIsEnriching] = useState(false)

  // Select a match - enrich profile and go to enrich step
  const handleSelect = async (match: ContactMatch) => {
    setSelectedMatch(match)
    setStep('enrich')
    
    // If we have a LinkedIn URL, fetch full profile data
    if (match.linkedin_url) {
      setIsEnriching(true)
      
      try {
        const { data, error } = await api.post<{
          success: boolean
          // New structured response
          about_section?: string  // Actual LinkedIn About text
          experience_section?: string  // Career history
          skills?: string[]
          ai_summary?: string  // AI-generated summary
          // Basic info
          headline?: string
          location?: string
          experience_years?: number
          error?: string
        }>('/api/v1/contacts/enrich', {
          linkedin_url: match.linkedin_url
        })
        
        if (!error && data?.success) {
          // Pre-fill About field - prioritize actual LinkedIn About section
          if (data.about_section) {
            // Use the actual About section from LinkedIn
            setLinkedinAbout(data.about_section)
          } else if (data.ai_summary) {
            // Fallback to AI summary if no About section found
            setLinkedinAbout(data.ai_summary)
          }
          
          // Pre-fill Experience field - combine experience, skills, and years
          const experienceParts: string[] = []
          
          // Add experience section if available
          if (data.experience_section) {
            experienceParts.push(data.experience_section)
          } else if (data.headline && data.headline !== match.title) {
            // Fallback to headline if no experience section
            experienceParts.push(`Current: ${data.headline}`)
          }
          
          // Add years of experience
          if (data.experience_years) {
            experienceParts.push(`\n${data.experience_years}+ years of experience`)
          }
          
          // Add skills as a separate section
          if (data.skills && data.skills.length > 0) {
            experienceParts.push(`\nKey Skills: ${data.skills.slice(0, 10).join(', ')}`)
          }
          
          if (experienceParts.length > 0) {
            setLinkedinExperience(experienceParts.join('\n'))
          }
          
          // Update the match with location if found
          if (data.location) {
            setSelectedMatch({ ...match, location: data.location })
          }
        }
      } catch (err) {
        console.log('Profile enrichment failed, continuing without enriched data:', err)
      } finally {
        setIsEnriching(false)
      }
    }
  }

  // Skip to manual entry (no LinkedIn found)
  const handleSkipSearch = () => {
    setSelectedMatch(null)
    setStep('confirm')
  }

  // Skip enrichment and go directly to confirm
  const handleSkipEnrich = () => {
    setStep('confirm')
  }

  // Go back
  const handleBack = () => {
    if (step === 'results') {
      setStep('search')
      setMatches([])
    } else if (step === 'enrich') {
      if (matches.length > 0) {
        setStep('results')
      } else {
        setStep('search')
      }
    } else if (step === 'confirm') {
      if (selectedMatch) {
        setStep('enrich')
      } else if (matches.length > 0) {
        setStep('results')
      } else {
        setStep('search')
      }
    }
  }

  // Add contact and start analysis
  const handleConfirm = async () => {
    const name = selectedMatch?.name || searchName
    if (!name.trim()) {
      toast({
        variant: 'destructive',
        title: t('contacts.search.nameLabel'),
        description: t('contacts.search.namePlaceholder')
      })
      return
    }

    setIsAdding(true)

    try {
      const { data, error } = await api.post<Contact>(
        `/api/v1/research/${researchId}/contacts`,
        {
          name: name.trim(),
          role: selectedMatch?.title || searchRole || null,
          linkedin_url: selectedMatch?.linkedin_url || null,
          email: email.trim() || null,
          phone: phone.trim() || null,
          is_primary: isPrimary,
          // User-provided LinkedIn info for richer analysis
          linkedin_about: linkedinAbout.trim() || null,
          linkedin_experience: linkedinExperience.trim() || null,
          additional_notes: additionalNotes.trim() || null
        }
      )

      if (error) {
        toast({
          variant: 'destructive',
          title: t('contacts.search.errorTitle'),
          description: error.message || t('contacts.search.errorAddFailed')
        })
        setIsAdding(false)
        return
      }

      if (data) {
        toast({
          title: '✅ ' + t('contacts.search.addAndAnalyze'),
          description: t('contacts.addedDesc')
        })
        onContactAdded(data)
        handleClose()
      }
    } catch (err) {
      toast({
        variant: 'destructive',
        title: t('contacts.search.errorTitle'),
        description: t('contacts.search.errorAddFailed')
      })
    } finally {
      setIsAdding(false)
    }
  }

  return (
    <Sheet open={isOpen} onOpenChange={(open) => !open && handleClose()}>
      <SheetContent side="right" className="sm:max-w-md overflow-y-auto">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            {step !== 'search' && step !== 'loading' && (
              <Button variant="ghost" size="icon" className="h-6 w-6 -ml-1" onClick={handleBack}>
                <Icons.arrowLeft className="h-4 w-4" />
              </Button>
            )}
            {step === 'search' && t('contacts.search.title')}
            {step === 'loading' && t('contacts.search.title')}
            {step === 'results' && t('contacts.search.resultsTitle')}
            {step === 'enrich' && t('contacts.search.enrichTitle')}
            {step === 'confirm' && t('contacts.search.confirmTitle')}
          </SheetTitle>
          <SheetDescription>
            {step === 'search' && t('contacts.search.subtitle', { company: companyName })}
          </SheetDescription>
        </SheetHeader>

        {/* Step 1: Search */}
        {step === 'search' && (
          <div className="space-y-4 mt-4">
            {/* Executives from Research - Quick Suggestions */}
            {executives.length > 0 && (
              <div className="space-y-2">
                <Label className="text-sm font-medium text-green-700 dark:text-green-400 flex items-center gap-1.5">
                  <Icons.users className="h-4 w-4" />
                  {t('contacts.search.suggestionsTitle') || 'Found in Research'}
                </Label>
                <div className="space-y-2 max-h-[180px] overflow-y-auto">
                  {executives.slice(0, 5).map((exec, index) => (
                    <button
                      key={`${exec.name}-${index}`}
                      onClick={() => handleSelectExecutive(exec)}
                      className="w-full text-left p-3 rounded-lg border border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-900/20 hover:bg-green-100 dark:hover:bg-green-900/40 transition-colors"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-green-900 dark:text-green-100 truncate">
                            {exec.name}
                          </p>
                          {exec.title && (
                            <p className="text-xs text-green-700 dark:text-green-400 truncate">
                              {exec.title}
                            </p>
                          )}
                        </div>
                        <div className="flex items-center gap-1 ml-2">
                          {exec.linkedin_url && (
                            <span className="text-xs bg-green-200 dark:bg-green-800 text-green-800 dark:text-green-200 px-1.5 py-0.5 rounded">
                              LinkedIn
                            </span>
                          )}
                          <Icons.arrowRight className="h-4 w-4 text-green-600 dark:text-green-400" />
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
                <div className="relative py-2">
                  <div className="absolute inset-0 flex items-center">
                    <span className="w-full border-t border-slate-200 dark:border-slate-700" />
                  </div>
                  <div className="relative flex justify-center text-xs uppercase">
                    <span className="bg-white dark:bg-slate-950 px-2 text-slate-500">
                      {t('contacts.search.orSearchManually') || 'or search manually'}
                    </span>
                  </div>
                </div>
              </div>
            )}

            {loadingExecutives && (
              <div className="flex items-center gap-2 text-sm text-slate-500">
                <Icons.spinner className="h-4 w-4 animate-spin" />
                {t('contacts.search.loadingSuggestions') || 'Loading suggestions...'}
              </div>
            )}

            <div className="space-y-3">
              <div>
                <Label htmlFor="search-name">{t('contacts.search.nameLabel')} *</Label>
                <Input
                  id="search-name"
                  placeholder={t('contacts.search.namePlaceholder')}
                  value={searchName}
                  onChange={(e) => setSearchName(e.target.value)}
                  className="mt-1"
                  onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                />
              </div>

              <div>
                <Label htmlFor="search-role">{t('contacts.search.roleLabel')}</Label>
                <Input
                  id="search-role"
                  placeholder={t('contacts.search.rolePlaceholder')}
                  value={searchRole}
                  onChange={(e) => setSearchRole(e.target.value)}
                  className="mt-1"
                  onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                />
              </div>
            </div>

            {error && (
              <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
                <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
              </div>
            )}

            <Button 
              onClick={handleSearch} 
              className="w-full"
              disabled={!searchName.trim()}
            >
              <Icons.search className="h-4 w-4 mr-2" />
              {t('contacts.search.searchButton')}
            </Button>

            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <span className="w-full border-t border-slate-200 dark:border-slate-700" />
              </div>
              <div className="relative flex justify-center text-xs uppercase">
                <span className="bg-white dark:bg-slate-950 px-2 text-slate-500">or</span>
              </div>
            </div>

            <Button 
              variant="outline" 
              onClick={handleSkipSearch}
              className="w-full"
            >
              <Icons.plus className="h-4 w-4 mr-2" />
              {t('contacts.search.skipSearch')}
            </Button>
          </div>
        )}

        {/* Step 1.5: Loading */}
        {step === 'loading' && (
          <div className="flex flex-col items-center justify-center py-12 space-y-4 mt-4">
            <Icons.spinner className="h-8 w-8 animate-spin text-blue-500" />
            <p className="text-sm text-slate-600 dark:text-slate-400">
              Searching for "{searchName}" at {companyName}...
            </p>
          </div>
        )}

        {/* Step 2: Results */}
        {step === 'results' && (
          <div className="space-y-4 mt-4">
            <p className="text-sm text-slate-600 dark:text-slate-400">
              {t('contacts.search.resultsSubtitle', { name: searchName, company: companyName })}
            </p>

            {matches.length > 0 ? (
              <div className="space-y-3 max-h-[400px] overflow-y-auto pr-1">
                {matches.map((match, index) => (
                  <ContactMatchCard
                    key={match.linkedin_url || index}
                    match={match}
                    isSelected={selectedMatch?.linkedin_url === match.linkedin_url}
                    onSelect={() => handleSelect(match)}
                  />
                ))}
              </div>
            ) : (
              <div className="text-center py-8">
                <Icons.search className="h-12 w-12 mx-auto text-slate-300 dark:text-slate-600 mb-3" />
                <p className="text-slate-600 dark:text-slate-400">{t('contacts.search.noResults')}</p>
              </div>
            )}

            <div className="border-t border-slate-200 dark:border-slate-700 pt-4">
              <Button 
                variant="outline" 
                onClick={handleSkipSearch}
                className="w-full"
              >
                <Icons.plus className="h-4 w-4 mr-2" />
                {t('contacts.search.addManually')}
              </Button>
            </div>
          </div>
        )}

        {/* Step 2.5: Enrich with LinkedIn Info */}
        {step === 'enrich' && selectedMatch && (
          <div className="space-y-4 mt-4">
            {/* Selected profile summary */}
            <div className="p-3 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
              <div className="flex items-center gap-2 text-blue-900 dark:text-blue-100 font-medium text-sm">
                <span>✓</span>
                <span>{selectedMatch.name}</span>
                {selectedMatch.title && <span className="text-blue-600 dark:text-blue-400">• {selectedMatch.title}</span>}
              </div>
              {selectedMatch.location && (
                <div className="text-xs text-blue-600 dark:text-blue-400 mt-1">📍 {selectedMatch.location}</div>
              )}
            </div>

            {/* Show loading state while enriching */}
            {isEnriching ? (
              <div className="p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
                <div className="flex items-center gap-3">
                  <Icons.spinner className="h-5 w-5 text-blue-600 dark:text-blue-400 animate-spin" />
                  <div className="text-sm text-blue-800 dark:text-blue-200">
                    <p className="font-medium">Fetching profile data...</p>
                    <p className="text-blue-600 dark:text-blue-400">This may take a few seconds</p>
                  </div>
                </div>
              </div>
            ) : (linkedinAbout || linkedinExperience) ? (
              <div className="p-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg">
                <div className="flex items-start gap-3">
                  <Icons.check className="h-5 w-5 text-green-600 dark:text-green-400 mt-0.5 flex-shrink-0" />
                  <div className="text-sm text-green-800 dark:text-green-200 flex-1">
                    <p className="font-medium mb-1">Profile data found!</p>
                    <p className="text-green-700 dark:text-green-300">
                      We automatically filled the fields below. Review and edit if needed, or add more details.
                    </p>
                    {selectedMatch.linkedin_url && (
                      <Button
                        variant="outline"
                        size="sm"
                        className="mt-2 bg-white dark:bg-slate-900 border-green-300 dark:border-green-700 text-green-800 dark:text-green-200 hover:bg-green-100 dark:hover:bg-green-900/40"
                        onClick={() => window.open(selectedMatch.linkedin_url!, '_blank')}
                      >
                        <Icons.link className="h-4 w-4 mr-2" />
                        {t('contacts.search.openLinkedIn')}
                      </Button>
                    )}
                  </div>
                </div>
              </div>
            ) : (
              <div className="p-4 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg">
                <div className="flex items-start gap-3">
                  <Icons.lightbulb className="h-5 w-5 text-amber-600 dark:text-amber-400 mt-0.5 flex-shrink-0" />
                  <div className="text-sm text-amber-800 dark:text-amber-200 flex-1">
                    <p className="font-medium mb-1">{t('contacts.search.enrichTip')}</p>
                    <p className="text-amber-700 dark:text-amber-300 mb-3">{t('contacts.search.enrichDescription')}</p>
                    {selectedMatch.linkedin_url ? (
                      <Button
                        variant="outline"
                        size="sm"
                        className="bg-white dark:bg-slate-900 border-amber-300 dark:border-amber-700 text-amber-800 dark:text-amber-200 hover:bg-amber-100 dark:hover:bg-amber-900/40"
                        onClick={() => window.open(selectedMatch.linkedin_url!, '_blank')}
                      >
                        <Icons.link className="h-4 w-4 mr-2" />
                        {t('contacts.search.openLinkedIn')}
                      </Button>
                    ) : (
                      <Button
                        variant="outline"
                        size="sm"
                        className="bg-white dark:bg-slate-900 border-amber-300 dark:border-amber-700 text-amber-800 dark:text-amber-200 hover:bg-amber-100 dark:hover:bg-amber-900/40"
                        onClick={() => {
                          const query = encodeURIComponent(`"${selectedMatch.name}" "${companyName}" linkedin`)
                          window.open(`https://www.google.com/search?q=${query}`, '_blank')
                        }}
                      >
                        <Icons.search className="h-4 w-4 mr-2" />
                        {t('contacts.search.searchLinkedIn') || 'Search on LinkedIn'}
                      </Button>
                    )}
                  </div>
                </div>
              </div>
            )}

            <div className="space-y-4">
              {/* About Section - LinkedIn's "About" / Summary */}
              <div>
                <Label htmlFor="linkedin-about" className="text-sm font-medium flex items-center gap-1.5">
                  About (LinkedIn)
                  {linkedinAbout && <span className="text-xs text-green-600 dark:text-green-400">(from profile)</span>}
                </Label>
                <p className="text-xs text-slate-500 dark:text-slate-400 mb-1.5">
                  {linkedinAbout 
                    ? 'This is their LinkedIn "About" section. Review and edit if needed.'
                    : 'Copy their LinkedIn "About" section here, or describe who they are.'
                  }
                </p>
                <Textarea
                  id="linkedin-about"
                  placeholder="Paste their LinkedIn About section or write a brief summary of who they are..."
                  value={linkedinAbout}
                  onChange={(e) => setLinkedinAbout(e.target.value)}
                  className={`min-h-[100px] text-sm ${linkedinAbout ? 'border-green-300 dark:border-green-700' : ''}`}
                />
              </div>

              {/* Experience & Skills Section */}
              <div>
                <Label htmlFor="linkedin-experience" className="text-sm font-medium flex items-center gap-1.5">
                  Experience & Skills
                  {linkedinExperience && <span className="text-xs text-green-600 dark:text-green-400">(from profile)</span>}
                </Label>
                <p className="text-xs text-slate-500 dark:text-slate-400 mb-1.5">
                  {linkedinExperience
                    ? 'Career history and skills from their profile. Add more details if available.'
                    : 'Add their work experience, past roles, and key skills.'
                  }
                </p>
                <Textarea
                  id="linkedin-experience"
                  placeholder="Current role, past positions, years of experience, key skills..."
                  value={linkedinExperience}
                  onChange={(e) => setLinkedinExperience(e.target.value)}
                  className={`min-h-[100px] text-sm ${linkedinExperience ? 'border-green-300 dark:border-green-700' : ''}`}
                />
              </div>

              {/* Your Notes Section */}
              <div>
                <Label htmlFor="additional-notes" className="text-sm font-medium">
                  Your Notes
                </Label>
                <p className="text-xs text-slate-500 dark:text-slate-400 mb-1.5">
                  Add any personal observations, meeting notes, or context that could help.
                </p>
                <Textarea
                  id="additional-notes"
                  placeholder='E.g. "Met at event X", "Referred by John", "Interested in our product Y"...'
                  value={additionalNotes}
                  onChange={(e) => setAdditionalNotes(e.target.value)}
                  className="min-h-[60px] text-sm"
                />
              </div>
            </div>

            <div className="flex gap-2 pt-2">
              <Button 
                variant="outline"
                onClick={handleSkipEnrich}
                className="flex-1"
              >
                {t('contacts.search.skipEnrich')}
              </Button>
              <Button 
                onClick={() => setStep('confirm')}
                className="flex-1"
              >
                <Icons.arrowRight className="h-4 w-4 mr-2" />
                {t('contacts.search.continueButton')}
              </Button>
            </div>
          </div>
        )}

        {/* Step 3: Confirm */}
        {step === 'confirm' && (
          <div className="space-y-4 mt-4">
            {selectedMatch ? (
              <>
                <p className="text-sm text-slate-600 dark:text-slate-400 font-medium">
                  {t('contacts.search.selectedProfile')}
                </p>
                <div className="p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
                  <div className="flex items-center gap-2 text-blue-900 dark:text-blue-100 font-medium">
                    <span>👤</span>
                    <span>{selectedMatch.name}</span>
                  </div>
                  {(selectedMatch.title || selectedMatch.company) && (
                    <p className="text-sm text-blue-700 dark:text-blue-300 mt-1">
                      {selectedMatch.title}
                      {selectedMatch.title && selectedMatch.company && ' @ '}
                      {selectedMatch.company}
                    </p>
                  )}
                  {selectedMatch.linkedin_url && (
                    <div className="flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400 mt-2">
                      <Icons.link className="h-3 w-3" />
                      <span className="truncate">{selectedMatch.linkedin_url}</span>
                    </div>
                  )}
                </div>
              </>
            ) : (
              <>
                <div className="p-4 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg">
                  <p className="text-sm text-amber-700 dark:text-amber-300">
                    Adding "{searchName}" manually without LinkedIn profile
                  </p>
                </div>
                
                {/* Notes field for manual entry - since we skip the enrich step */}
                <div>
                  <Label htmlFor="manual-notes" className="text-sm font-medium flex items-center gap-1">
                    <Icons.lightbulb className="h-3 w-3 text-amber-500" />
                    {t('contacts.search.notesLabel') || 'Eigen notities'}
                  </Label>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mb-1.5">
                    {t('contacts.search.manualNotesHint') || 'Deel wat je al weet over deze persoon (achtergrond, relatie, gesprekken, etc.)'}
                  </p>
                  <Textarea
                    id="manual-notes"
                    placeholder={t('contacts.search.notesPlaceholder') || 'Bijv. "Ontmoet op event X", "Geïntroduceerd door Jan", "Geïnteresseerd in ons product Y"...'}
                    value={additionalNotes}
                    onChange={(e) => setAdditionalNotes(e.target.value)}
                    className="min-h-[80px] text-sm"
                  />
                </div>
              </>
            )}

            <div className="space-y-3">
              <p className="text-sm font-medium text-slate-700 dark:text-slate-300">
                {t('contacts.search.extraInfo')}
              </p>

              <div>
                <Label htmlFor="confirm-email">{t('contacts.search.emailLabel')}</Label>
                <Input
                  id="confirm-email"
                  type="email"
                  placeholder="jan@company.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="mt-1"
                />
              </div>

              <div>
                <Label htmlFor="confirm-phone">{t('contacts.search.phoneLabel')}</Label>
                <Input
                  id="confirm-phone"
                  type="tel"
                  placeholder="+31 6 1234 5678"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  className="mt-1"
                />
              </div>

              <div className="flex items-center space-x-2">
                <Checkbox 
                  id="primary-contact" 
                  checked={isPrimary}
                  onCheckedChange={(checked) => setIsPrimary(checked === true)}
                />
                <Label htmlFor="primary-contact" className="text-sm font-normal cursor-pointer">
                  {t('contacts.search.primaryContact')}
                </Label>
              </div>
            </div>

            <Button 
              onClick={handleConfirm}
              className="w-full"
              disabled={isAdding}
            >
              {isAdding ? (
                <>
                  <Icons.spinner className="h-4 w-4 mr-2 animate-spin" />
                  Adding...
                </>
              ) : (
                <>
                  <Icons.plus className="h-4 w-4 mr-2" />
                  {t('contacts.search.addAndAnalyze')}
                </>
              )}
            </Button>
          </div>
        )}
      </SheetContent>
    </Sheet>
  )
}
