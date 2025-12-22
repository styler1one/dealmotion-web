"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { createClientComponentClient } from '@supabase/auth-helpers-nextjs'
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Loader2, CheckCircle2, ArrowRight, Sparkles, Wand2 } from "lucide-react"
import { useTranslations } from 'next-intl'
import { LanguageSelector } from '@/components/language-selector'
import { useLocale } from 'next-intl'
import type { Locale } from '@/i18n/config'
import { getErrorMessage } from '@/lib/error-utils'
import { logger } from '@/lib/logger'

interface InterviewResponse {
  session_id: string
  question_id?: number
  question?: string
  progress: number
  total_questions: number
  completed?: boolean
}

export default function OnboardingPage() {
  const router = useRouter()
  const t = useTranslations('onboarding')
  const tCommon = useTranslations('common')
  const locale = useLocale() as Locale
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [currentQuestionId, setCurrentQuestionId] = useState<number | null>(null)
  const [currentQuestionText, setCurrentQuestionText] = useState<string>("")  
  const [currentProgress, setCurrentProgress] = useState<number>(0)
  const [totalQuestions, setTotalQuestions] = useState<number>(15)
  const [answer, setAnswer] = useState("")
  const [responses, setResponses] = useState<Record<number, string>>({})
  const [loading, setLoading] = useState(false)
  const [starting, setStarting] = useState(true)
  const [completing, setCompleting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [hasExistingProfile, setHasExistingProfile] = useState(false)
  const [showExistingProfilePrompt, setShowExistingProfilePrompt] = useState(false)

  useEffect(() => {
    checkProfileAndStartInterview()
  }, [])

  const checkProfileAndStartInterview = async () => {
    setStarting(true)
    setError(null)
    
    try {
      const token = await getAuthToken()
      if (!token) {
        // getAuthToken already handles redirect to /login
        return
      }

      // First check if profile already exists
      const checkResponse = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/v1/profile/sales/check`,
        {
          method: "GET",
          headers: {
            "Authorization": `Bearer ${token}`,
          },
        }
      )

      if (checkResponse.ok) {
        const checkData = await checkResponse.json()
        if (checkData.exists) {
          // Profile already exists, show prompt
          setHasExistingProfile(true)
          setShowExistingProfilePrompt(true)
          setStarting(false)
          return
        }
      }

      // Profile doesn't exist, start interview
      await startInterview()
    } catch (err) {
      console.error('[ONBOARDING] Error checking profile:', err)
      // If check fails, try to start interview anyway
      await startInterview()
    }
  }

  const getAuthToken = async () => {
    const supabase = createClientComponentClient()
    const { data: { session } } = await supabase.auth.getSession()
    if (!session) {
      router.push("/login")
      return null
    }
    return session.access_token
  }

  const startInterview = async () => {
    try {
      const token = await getAuthToken()
      if (!token) return

      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/v1/profile/sales/interview/start`,
        {
          method: "POST",
          headers: {
            "Authorization": `Bearer ${token}`,
            "Content-Type": "application/json",
          },
        }
      )

      if (!response.ok) {
        throw new Error("Failed to start interview")
      }

      const data: InterviewResponse = await response.json()
      setSessionId(data.session_id)
      if (data.question_id) setCurrentQuestionId(data.question_id)
      if (data.question) setCurrentQuestionText(data.question)
      setCurrentProgress(data.progress)
      setTotalQuestions(data.total_questions)
    } catch (err) {
      const message = getErrorMessage(err)
      setError(t('errors.startFailed'))
      logger.error('Failed to start interview', err, { source: 'OnboardingPage', details: message })
    } finally {
      setStarting(false)
    }
  }

  const submitAnswer = async () => {
    if (!answer.trim() || !sessionId || !currentQuestionId) return

    setLoading(true)
    setError(null)

    try {
      const token = await getAuthToken()
      if (!token) return

      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/v1/profile/sales/interview/answer`,
        {
          method: "POST",
          headers: {
            "Authorization": `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            session_id: sessionId,
            question_id: currentQuestionId,
            answer: answer,
          }),
        }
      )

      if (!response.ok) {
        throw new Error("Failed to submit answer")
      }

      const data: InterviewResponse = await response.json()
      
      // Save the answer we just submitted
      if (currentQuestionId) {
        setResponses(prev => ({ ...prev, [currentQuestionId]: answer }))
      }
      
      // Check if interview is complete
      if (data.completed || data.progress >= data.total_questions) {
        await completeInterview()
      } else {
        if (data.question_id) setCurrentQuestionId(data.question_id)
        if (data.question) setCurrentQuestionText(data.question)
        setCurrentProgress(data.progress)
        setTotalQuestions(data.total_questions)
        setAnswer("")
      }
    } catch (err) {
      const message = getErrorMessage(err)
      setError(t('errors.submitFailed'))
      logger.error('Failed to submit answer', err, { source: 'OnboardingPage', details: message })
    } finally {
      setLoading(false)
    }
  }

  const completeInterview = async () => {
    if (!sessionId) return

    setCompleting(true)
    setError(null)

    try {
      const token = await getAuthToken()
      if (!token) return

      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/v1/profile/sales/interview/complete`,
        {
          method: "POST",
          headers: {
            "Authorization": `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            session_id: sessionId,
            responses: responses,
          }),
        }
      )

      if (!response.ok) {
        throw new Error("Failed to complete interview")
      }

      // Redirect to dashboard after successful completion
      router.push("/dashboard?onboarding=complete")
    } catch (err) {
      setError("Failed to complete interview. Please try again.")
      console.error(err)
      setCompleting(false)
    }
  }

  const progressPercentage = (currentProgress / totalQuestions) * 100

  // Show prompt for existing profile
  if (showExistingProfilePrompt) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 dark:from-gray-900 dark:to-gray-800 px-4">
        <Card className="w-full max-w-lg">
          <CardHeader>
            <div className="flex items-center gap-3 mb-2">
              <CheckCircle2 className="h-8 w-8 text-green-600" />
              <CardTitle className="text-2xl">{t('existingProfile.title')}</CardTitle>
            </div>
            <CardDescription>
              {t('existingProfile.description')}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="rounded-lg bg-muted p-4">
              <h4 className="font-semibold mb-2">What happens when you continue?</h4>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li className="flex items-start gap-2">
                  <Sparkles className="h-4 w-4 mt-0.5 text-blue-600" />
                  <span>Your answers will be analyzed by AI to update your profile</span>
                </li>
                <li className="flex items-start gap-2">
                  <Sparkles className="h-4 w-4 mt-0.5 text-blue-600" />
                  <span>Your existing profile will be enhanced with new insights</span>
                </li>
                <li className="flex items-start gap-2">
                  <Sparkles className="h-4 w-4 mt-0.5 text-blue-600" />
                  <span>AI agents will have better context for personalization</span>
                </li>
              </ul>
            </div>
          </CardContent>
          <CardFooter className="flex gap-3">
            <Button
              variant="outline"
              onClick={() => router.push("/dashboard")}
              className="flex-1"
            >
              {t('goToDashboard')}
            </Button>
            <Button
              onClick={() => {
                setShowExistingProfilePrompt(false)
                startInterview()
              }}
              className="flex-1"
            >
              <Sparkles className="mr-2 h-4 w-4" />
              {t('updateProfile')}
            </Button>
          </CardFooter>
        </Card>
      </div>
    )
  }

  if (starting) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 dark:from-gray-900 dark:to-gray-800">
        <Card className="w-full max-w-md">
          <CardContent className="pt-6">
            <div className="flex flex-col items-center space-y-4">
              <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
              <p className="text-sm text-muted-foreground">{t('starting')}</p>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  // Show choice between Magic and Traditional onboarding for new users
  if (!hasExistingProfile && !sessionId) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 dark:from-gray-900 dark:to-gray-800 px-4">
        <div className="absolute top-4 right-4">
          <LanguageSelector currentLocale={locale} />
        </div>
        
        <div className="w-full max-w-3xl">
          <div className="text-center mb-8">
            <Sparkles className="h-12 w-12 text-blue-600 mx-auto mb-4" />
            <h1 className="text-3xl font-bold mb-2">{t('welcome')}</h1>
            <p className="text-muted-foreground">Choose how you want to set up your sales profile</p>
          </div>
          
          <div className="grid md:grid-cols-2 gap-6">
            {/* Magic Option */}
            <Card className="shadow-lg hover:shadow-xl transition-shadow cursor-pointer border-2 hover:border-violet-400"
                  onClick={() => router.push('/onboarding/magic')}>
              <CardHeader className="text-center pb-2">
                <div className="w-16 h-16 rounded-full bg-gradient-to-br from-violet-500 to-fuchsia-500 flex items-center justify-center mx-auto mb-3">
                  <Wand2 className="h-8 w-8 text-white" />
                </div>
                <CardTitle className="text-xl">Magic Setup</CardTitle>
                <CardDescription className="text-base">
                  Just paste your LinkedIn URL and we'll create your profile in seconds
                </CardDescription>
              </CardHeader>
              <CardContent className="text-center">
                <ul className="text-sm text-muted-foreground space-y-2 mb-4">
                  <li className="flex items-center justify-center gap-2">
                    <CheckCircle2 className="h-4 w-4 text-green-600" />
                    Auto-extract from LinkedIn
                  </li>
                  <li className="flex items-center justify-center gap-2">
                    <CheckCircle2 className="h-4 w-4 text-green-600" />
                    AI-enhanced profile
                  </li>
                  <li className="flex items-center justify-center gap-2">
                    <CheckCircle2 className="h-4 w-4 text-green-600" />
                    ~30 seconds
                  </li>
                </ul>
                <Button className="w-full bg-gradient-to-r from-violet-600 to-fuchsia-600">
                  <Wand2 className="h-4 w-4 mr-2" />
                  Start Magic Setup
                </Button>
              </CardContent>
            </Card>

            {/* Traditional Option */}
            <Card className="shadow-lg hover:shadow-xl transition-shadow cursor-pointer border-2 hover:border-blue-400"
                  onClick={() => startInterview()}>
              <CardHeader className="text-center pb-2">
                <div className="w-16 h-16 rounded-full bg-gradient-to-br from-blue-500 to-indigo-500 flex items-center justify-center mx-auto mb-3">
                  <Sparkles className="h-8 w-8 text-white" />
                </div>
                <CardTitle className="text-xl">Guided Interview</CardTitle>
                <CardDescription className="text-base">
                  Answer questions step-by-step to build your detailed profile
                </CardDescription>
              </CardHeader>
              <CardContent className="text-center">
                <ul className="text-sm text-muted-foreground space-y-2 mb-4">
                  <li className="flex items-center justify-center gap-2">
                    <CheckCircle2 className="h-4 w-4 text-green-600" />
                    {totalQuestions} personalized questions
                  </li>
                  <li className="flex items-center justify-center gap-2">
                    <CheckCircle2 className="h-4 w-4 text-green-600" />
                    Full control over answers
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
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 dark:from-gray-900 dark:to-gray-800">
        <Card className="w-full max-w-md">
          <CardContent className="pt-6">
            <div className="flex flex-col items-center space-y-4">
              <CheckCircle2 className="h-12 w-12 text-green-600" />
              <div className="text-center">
                <h3 className="text-lg font-semibold">{t('complete.title')}</h3>
                <p className="text-sm text-muted-foreground mt-2">
                  {t('complete.creating')}
                </p>
              </div>
              <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 dark:from-gray-900 dark:to-gray-800 py-12 px-4">
      {/* Language Selector */}
      <div className="absolute top-4 right-4">
        <LanguageSelector currentLocale={locale} />
      </div>
      
      <div className="max-w-3xl mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="flex items-center justify-center mb-4">
            <Sparkles className="h-8 w-8 text-blue-600 mr-2" />
            <h1 className="text-3xl font-bold">{t('welcome')}</h1>
          </div>
          <p className="text-muted-foreground">
            {t('welcomeDesc')}
          </p>
        </div>

        {/* Progress Bar */}
        <div className="mb-8">
          <div className="flex justify-between text-sm text-muted-foreground mb-2">
            <span>{t('question', { current: currentProgress, total: totalQuestions })}</span>
            <span>{Math.round(progressPercentage)}% {tCommon('complete')}</span>
          </div>
          <Progress value={progressPercentage} className="h-2" />
        </div>

        {/* Question Card */}
        <Card className="shadow-lg">
          <CardHeader>
            <CardTitle className="text-xl">
              {currentQuestionText}
            </CardTitle>
            <CardDescription>
              {t('takeYourTime')}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Textarea
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              placeholder={t('answerPlaceholder')}
              className="min-h-[150px] resize-none"
              disabled={loading}
            />
            {error && (
              <p className="text-sm text-red-600 mt-2">{error}</p>
            )}
          </CardContent>
          <CardFooter className="flex justify-between">
            <div className="text-sm text-muted-foreground">
              {answer.length} characters
            </div>
            <Button
              onClick={submitAnswer}
              disabled={!answer.trim() || loading}
              size="lg"
            >
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Submitting...
                </>
              ) : (
                <>
                  Next
                  <ArrowRight className="ml-2 h-4 w-4" />
                </>
              )}
            </Button>
          </CardFooter>
        </Card>

        {/* Tips */}
        <div className="mt-6 text-center">
          <p className="text-sm text-muted-foreground">
            💡 Tip: The more details you provide, the better we can personalize your experience
          </p>
        </div>
      </div>
    </div>
  )
}
