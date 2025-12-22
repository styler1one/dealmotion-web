'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { createClientComponentClient } from '@supabase/auth-helpers-nextjs'
import { useTranslations, useLocale } from 'next-intl'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { useToast } from '@/components/ui/use-toast'
import { LanguageSelector } from '@/components/language-selector'
import type { Locale } from '@/i18n/config'
import { 
  ArrowLeft, 
  ArrowRight, 
  Building2, 
  Loader2,
  CheckCircle2,
  Sparkles,
  Wand2
} from 'lucide-react'

interface InterviewState {
  sessionId: string
  questionId: number
  question: string
  progress: number
  totalQuestions: number
}

export default function CompanyOnboardingPage() {
  const router = useRouter()
  const supabase = createClientComponentClient()
  const { toast } = useToast()
  const t = useTranslations('onboarding')
  const locale = useLocale() as Locale
  
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [completing, setCompleting] = useState(false)
  const [interview, setInterview] = useState<InterviewState | null>(null)
  const [answer, setAnswer] = useState('')
  const [responses, setResponses] = useState<Record<number, string>>({})
  const [completed, setCompleted] = useState(false)
  const [showChoice, setShowChoice] = useState(true)

  // Check auth on mount
  useEffect(() => {
    const checkAuth = async () => {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) {
        router.push('/login')
        return
      }
      setLoading(false)
    }
    checkAuth()
  }, [supabase, router])

  const startInterview = async () => {
    setShowChoice(false)
    setLoading(true)
    try {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) {
        router.push('/login')
        return
      }

      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/v1/profile/company/interview/start`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${session.access_token}`,
            'Content-Type': 'application/json'
          }
        }
      )

      if (!response.ok) {
        throw new Error('Failed to start interview')
      }

      const data = await response.json()
      setInterview({
        sessionId: data.session_id,
        questionId: data.question_id,
        question: data.question,
        progress: data.progress,
        totalQuestions: data.total_questions
      })
    } catch (error) {
      console.error('Error starting interview:', error)
      toast({
        title: t('toast.startError'),
        description: t('toast.startErrorDesc'),
        variant: 'destructive'
      })
    } finally {
      setLoading(false)
    }
  }

  const handleSubmitAnswer = async () => {
    if (!interview || !answer.trim()) return
    
    setSubmitting(true)
    
    try {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) return

      // Store answer locally
      const updatedResponses = { 
        ...responses, 
        [interview.questionId]: answer 
      }
      setResponses(updatedResponses)

      // Submit to backend
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/v1/profile/company/interview/answer`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${session.access_token}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            session_id: interview.sessionId,
            question_id: interview.questionId,
            answer: answer
          })
        }
      )

      if (!response.ok) {
        throw new Error('Failed to submit answer')
      }

      const data = await response.json()
      
      if (data.completed) {
        // Interview done, complete it
        setCompleted(true)
        await handleCompleteInterview(updatedResponses)
      } else {
        // Move to next question
        setInterview({
          ...interview,
          questionId: data.question_id,
          question: data.question,
          progress: data.progress,
          totalQuestions: data.total_questions
        })
        setAnswer('')
      }
    } catch (error) {
      console.error('Error submitting answer:', error)
      toast({
        title: t('toast.saveError'),
        description: t('toast.saveErrorDesc'),
        variant: 'destructive'
      })
    } finally {
      setSubmitting(false)
    }
  }

  const handleCompleteInterview = async (allResponses: Record<number, string>) => {
    if (!interview) return
    
    setCompleting(true)
    
    try {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) return

      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/v1/profile/company/interview/complete`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${session.access_token}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            session_id: interview.sessionId,
            responses: allResponses
          })
        }
      )

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Failed to complete interview')
      }

      toast({
        title: t('toast.profileCreated'),
        description: t('toast.profileCreatedDesc')
      })

      // Redirect to company profile page
      router.push('/dashboard/company-profile')
      
    } catch (error) {
      console.error('Error completing interview:', error)
      toast({
        title: t('toast.createError'),
        description: error instanceof Error ? error.message : t('toast.createErrorDesc'),
        variant: 'destructive'
      })
      setCompleted(false)
    } finally {
      setCompleting(false)
    }
  }

  const handleSkip = () => {
    // Submit empty answer and move to next question
    if (!interview) return
    
    const updatedResponses = { 
      ...responses, 
      [interview.questionId]: '' 
    }
    setResponses(updatedResponses)
    
    // Get next question
    handleSubmitAnswer()
  }

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin text-primary mx-auto mb-4" />
          <p className="text-muted-foreground">{t('company.startInterview')}</p>
        </div>
      </div>
    )
  }

  // Show choice between Magic and Traditional onboarding
  if (showChoice && !interview) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-50 px-4">
        <div className="absolute top-4 right-4">
          <LanguageSelector currentLocale={locale} />
        </div>
        
        <div className="w-full max-w-3xl">
          <Button 
            variant="ghost" 
            onClick={() => router.push('/dashboard')}
            className="mb-6"
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            {t('back')}
          </Button>
          
          <div className="text-center mb-8">
            <Building2 className="h-12 w-12 text-blue-600 mx-auto mb-4" />
            <h1 className="text-3xl font-bold mb-2">{t('company.pageTitle')}</h1>
            <p className="text-muted-foreground">Choose how you want to set up your company profile</p>
          </div>
          
          <div className="grid md:grid-cols-2 gap-6">
            {/* Magic Option */}
            <Card className="shadow-lg hover:shadow-xl transition-shadow cursor-pointer border-2 hover:border-blue-400"
                  onClick={() => router.push('/onboarding/company/magic')}>
              <CardHeader className="text-center pb-2">
                <div className="w-16 h-16 rounded-full bg-gradient-to-br from-blue-500 to-indigo-500 flex items-center justify-center mx-auto mb-3">
                  <Wand2 className="h-8 w-8 text-white" />
                </div>
                <CardTitle className="text-xl">Magic Setup</CardTitle>
                <CardDescription className="text-base">
                  Enter your company name and we'll research everything automatically
                </CardDescription>
              </CardHeader>
              <CardContent className="text-center">
                <ul className="text-sm text-muted-foreground space-y-2 mb-4">
                  <li className="flex items-center justify-center gap-2">
                    <CheckCircle2 className="h-4 w-4 text-green-600" />
                    AI-powered research
                  </li>
                  <li className="flex items-center justify-center gap-2">
                    <CheckCircle2 className="h-4 w-4 text-green-600" />
                    Auto-discover website & LinkedIn
                  </li>
                  <li className="flex items-center justify-center gap-2">
                    <CheckCircle2 className="h-4 w-4 text-green-600" />
                    ~1 minute
                  </li>
                </ul>
                <Button className="w-full bg-gradient-to-r from-blue-600 to-indigo-600">
                  <Wand2 className="h-4 w-4 mr-2" />
                  Start Magic Setup
                </Button>
              </CardContent>
            </Card>

            {/* Traditional Option */}
            <Card className="shadow-lg hover:shadow-xl transition-shadow cursor-pointer border-2 hover:border-indigo-400"
                  onClick={() => startInterview()}>
              <CardHeader className="text-center pb-2">
                <div className="w-16 h-16 rounded-full bg-gradient-to-br from-indigo-500 to-purple-500 flex items-center justify-center mx-auto mb-3">
                  <Sparkles className="h-8 w-8 text-white" />
                </div>
                <CardTitle className="text-xl">Guided Interview</CardTitle>
                <CardDescription className="text-base">
                  Answer questions step-by-step to build your company profile
                </CardDescription>
              </CardHeader>
              <CardContent className="text-center">
                <ul className="text-sm text-muted-foreground space-y-2 mb-4">
                  <li className="flex items-center justify-center gap-2">
                    <CheckCircle2 className="h-4 w-4 text-green-600" />
                    12 focused questions
                  </li>
                  <li className="flex items-center justify-center gap-2">
                    <CheckCircle2 className="h-4 w-4 text-green-600" />
                    Full control over content
                  </li>
                  <li className="flex items-center justify-center gap-2">
                    <CheckCircle2 className="h-4 w-4 text-green-600" />
                    ~10-15 minutes
                  </li>
                </ul>
                <Button variant="outline" className="w-full">
                  <ArrowRight className="h-4 w-4 mr-2" />
                  Start Interview
                </Button>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    )
  }

  if (completing) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="text-center max-w-md px-4">
          <Sparkles className="h-12 w-12 text-primary mx-auto mb-4 animate-pulse" />
          <h2 className="text-2xl font-bold mb-2">{t('company.generating')}</h2>
          <p className="text-muted-foreground mb-4">
            {t('company.generatingDesc')}
          </p>
          <div className="flex items-center justify-center gap-2">
            <Loader2 className="h-5 w-5 animate-spin" />
            <span className="text-sm text-muted-foreground">{t('company.generatingWait')}</span>
          </div>
        </div>
      </div>
    )
  }

  if (!interview) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="text-center">
          <Building2 className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
          <p className="text-muted-foreground">{t('company.couldNotLoad')}</p>
          <Button 
            variant="outline" 
            onClick={() => router.push('/dashboard')}
            className="mt-4"
          >
            Terug naar Dashboard
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-50 py-8 px-4">
      {/* Language Selector */}
      <div className="absolute top-4 right-4">
        <LanguageSelector currentLocale={locale} />
      </div>
      
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <Button 
            variant="ghost" 
            onClick={() => router.push('/dashboard')}
            className="mb-4"
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            {t('back')}
          </Button>
          
          <div className="flex items-center gap-3 mb-4">
            <div className="p-3 bg-primary/10 rounded-full">
              <Building2 className="h-8 w-8 text-primary" />
            </div>
            <div>
              <h1 className="text-2xl font-bold">{t('company.pageTitle')}</h1>
              <p className="text-muted-foreground">
                {t('company.pageDesc')}
              </p>
            </div>
          </div>

          {/* Progress */}
          <div className="mb-2 flex items-center justify-between text-sm">
            <span className="text-muted-foreground">
              {t('company.questionOf', { current: interview.progress, total: interview.totalQuestions })}
            </span>
            <span className="font-medium">
              {Math.round((interview.progress / interview.totalQuestions) * 100)}%
            </span>
          </div>
          <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
            <div 
              className="h-full bg-primary transition-all duration-300"
              style={{ width: `${(interview.progress / interview.totalQuestions) * 100}%` }}
            />
          </div>
        </div>

        {/* Question Card */}
        <Card className="mb-6 shadow-lg">
          <CardHeader>
            <CardTitle className="text-lg">
              {interview.question}
            </CardTitle>
            <CardDescription>
              {interview.progress <= 6 
                ? t('company.requiredQuestion')
                : t('company.optionalQuestion')}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Textarea
              placeholder={t('company.answerPlaceholder')}
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              rows={5}
              className="resize-none"
              autoFocus
            />
          </CardContent>
        </Card>

        {/* Actions */}
        <div className="flex items-center justify-between">
          {interview.progress > 6 ? (
            <Button 
              variant="ghost" 
              onClick={handleSkip}
              disabled={submitting}
            >
              Overslaan
            </Button>
          ) : (
            <div />
          )}
          
          <Button 
            onClick={handleSubmitAnswer}
            disabled={submitting || (!answer.trim() && interview.progress <= 6)}
            className="gap-2"
          >
            {submitting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Opslaan...
              </>
            ) : interview.progress === interview.totalQuestions ? (
              <>
                <CheckCircle2 className="h-4 w-4" />
                Afronden
              </>
            ) : (
              <>
                Volgende
                <ArrowRight className="h-4 w-4" />
              </>
            )}
          </Button>
        </div>

        {/* Tips */}
        <Card className="mt-8 bg-muted/50 border-none">
          <CardContent className="pt-6">
            <h3 className="font-medium mb-2 flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-yellow-500" />
              Tip
            </h3>
            <p className="text-sm text-muted-foreground">
              {interview.progress === 1 && "Begin met de officiële naam van je bedrijf"}
              {interview.progress === 2 && "Denk aan de sector waarin je actief bent (bijv. SaaS, Consulting, Retail)"}
              {interview.progress === 3 && "Beschrijf je belangrijkste producten of diensten en hun waarde"}
              {interview.progress === 4 && "Wat maakt jullie uniek? Denk aan technologie, aanpak, service"}
              {interview.progress === 5 && "Wie zijn je beste klanten? Welke bedrijven passen perfect?"}
              {interview.progress === 6 && "Welke problemen los je op? Waarom komen klanten naar jullie?"}
              {interview.progress > 6 && "Deze informatie helpt de AI nog beter gepersonaliseerde content te maken"}
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

