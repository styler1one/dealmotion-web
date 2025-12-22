'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { useTranslations } from 'next-intl';
import { 
  Sparkles, 
  Linkedin, 
  ArrowRight, 
  Loader2,
  CheckCircle2,
  AlertCircle
} from 'lucide-react';
import ProfileChat from '@/components/onboarding/ProfileChat';

type Step = 'linkedin' | 'enriching' | 'chat' | 'complete';

export default function ChatOnboardingPage() {
  const router = useRouter();
  const t = useTranslations('onboarding.chat');
  const [step, setStep] = useState<Step>('linkedin');
  const [linkedinUrl, setLinkedinUrl] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [linkedinData, setLinkedinData] = useState<Record<string, any>>({});
  const [userName, setUserName] = useState<string>('');

  // Check for existing profile on mount
  useEffect(() => {
    checkExistingProfile();
  }, []);

  const checkExistingProfile = async () => {
    try {
      const response = await fetch('/api/v1/profile', {
        credentials: 'include'
      });
      if (response.ok) {
        const data = await response.json();
        if (data.full_name) {
          setUserName(data.full_name);
          // Pre-fill LinkedIn URL if available
          if (data.linkedin_url) {
            setLinkedinUrl(data.linkedin_url);
          }
        }
      }
    } catch (e) {
      // Ignore - new user
    }
  };

  const enrichLinkedIn = async () => {
    if (!linkedinUrl.trim()) return;

    setIsLoading(true);
    setError(null);
    setStep('enriching');

    try {
      // Get auth token
      const supabase = (await import('@supabase/auth-helpers-nextjs')).createClientComponentClient();
      const { data: { session } } = await supabase.auth.getSession();
      
      if (!session) {
        router.push('/login');
        return;
      }
      
      // Call magic onboarding to get LinkedIn data
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/profile/sales/magic/start`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${session.access_token}`
        },
        body: JSON.stringify({
          linkedin_url: linkedinUrl.trim()
        })
      });

      if (!response.ok) {
        throw new Error('Kon LinkedIn profiel niet ophalen');
      }

      const data = await response.json();
      
      // Poll for completion (Inngest job)
      if (data.session_id) {
        await pollForCompletion(data.session_id);
      } else if (data.profile_data) {
        // Direct result (fallback)
        setLinkedinData(data.profile_data);
        if (data.profile_data.full_name) {
          setUserName(data.profile_data.full_name);
        }
        setStep('chat');
      }
    } catch (err: any) {
      setError(err.message || 'Er ging iets mis');
      setStep('linkedin');
    } finally {
      setIsLoading(false);
    }
  };

  const pollForCompletion = async (sessionId: string) => {
    const maxAttempts = 30;
    let attempts = 0;
    
    // Get auth token for polling
    const supabase = (await import('@supabase/auth-helpers-nextjs')).createClientComponentClient();
    const { data: { session } } = await supabase.auth.getSession();
    
    if (!session) {
      throw new Error('Not authenticated');
    }

    while (attempts < maxAttempts) {
      try {
        const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/profile/sales/magic/status/${sessionId}`, {
          headers: {
            'Authorization': `Bearer ${session.access_token}`
          }
        });

        if (!response.ok) throw new Error('Status check failed');

        const data = await response.json();

        if (data.status === 'completed') {
          // Backend returns profile_data directly, not nested in result
          const profileData = data.profile_data || {};
          const linkedinRaw = data.linkedin_data || {};
          
          // Merge LinkedIn raw data with profile data for richer context
          const mergedData = {
            ...profileData,
            linkedin_raw: linkedinRaw
          };
          
          setLinkedinData(mergedData);
          if (profileData.full_name) {
            setUserName(profileData.full_name);
          }
          setStep('chat');
          return;
        } else if (data.status === 'failed') {
          throw new Error(data.error || 'LinkedIn enrichment failed');
        }

        // Wait and retry
        await new Promise(resolve => setTimeout(resolve, 2000));
        attempts++;
      } catch (err) {
        throw err;
      }
    }

    throw new Error('Timeout: LinkedIn enrichment took too long');
  };

  const handleProfileComplete = (profile: Record<string, any>) => {
    setStep('complete');
    // Redirect after short delay
    setTimeout(() => {
      router.push('/dashboard');
    }, 2000);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-violet-950">
      {/* Background decoration */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-violet-500/10 rounded-full blur-3xl" />
        <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-fuchsia-500/10 rounded-full blur-3xl" />
      </div>

      <div className="relative max-w-2xl mx-auto px-4 py-12">
        {/* Header */}
        <div className="text-center mb-8">
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ type: 'spring', duration: 0.5 }}
            className="inline-flex p-4 rounded-2xl bg-gradient-to-br from-violet-500/20 to-fuchsia-500/20 border border-violet-500/30 mb-6"
          >
            <Sparkles className="w-8 h-8 text-violet-400" />
          </motion.div>
          
          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="text-3xl font-bold text-white mb-3"
          >
            {t('title')}
          </motion.h1>
          
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="text-slate-400"
          >
            {t('subtitle')}
          </motion.p>
        </div>

        {/* Steps indicator */}
        <div className="flex justify-center gap-2 mb-8">
          {['linkedin', 'chat', 'complete'].map((s, i) => (
            <div
              key={s}
              className={`h-2 rounded-full transition-all duration-500 ${
                step === s || (step === 'enriching' && s === 'linkedin')
                  ? 'w-8 bg-violet-500'
                  : (i < ['linkedin', 'enriching', 'chat', 'complete'].indexOf(step))
                    ? 'w-8 bg-violet-500/50'
                    : 'w-2 bg-slate-700'
              }`}
            />
          ))}
        </div>

        {/* Content */}
        <motion.div
          key={step}
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -20 }}
          transition={{ duration: 0.3 }}
        >
          {/* Step 1: LinkedIn URL */}
          {step === 'linkedin' && (
            <div className="bg-slate-800/50 backdrop-blur border border-slate-700/50 rounded-2xl p-8">
              <div className="flex items-center gap-3 mb-6">
                <div className="p-2 rounded-xl bg-blue-500/20">
                  <Linkedin className="w-6 h-6 text-blue-400" />
                </div>
                <div>
                  <h2 className="text-xl font-semibold text-white">
                    {t('startWithLinkedIn')}
                  </h2>
                  <p className="text-sm text-slate-400">
                    {t('startWithLinkedInDesc')}
                  </p>
                </div>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">
                    {t('linkedInUrlLabel')}
                  </label>
                  <input
                    type="url"
                    value={linkedinUrl}
                    onChange={(e) => setLinkedinUrl(e.target.value)}
                    placeholder={t('linkedInPlaceholder')}
                    className="w-full bg-slate-700/50 border border-slate-600 rounded-xl px-4 py-3 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-violet-500"
                  />
                </div>

                {error && (
                  <div className="flex items-center gap-2 text-red-400 text-sm">
                    <AlertCircle className="w-4 h-4" />
                    <span>{error}</span>
                  </div>
                )}

                <button
                  onClick={enrichLinkedIn}
                  disabled={!linkedinUrl.trim() || isLoading}
                  className="w-full py-3 px-4 bg-gradient-to-r from-violet-600 to-fuchsia-600 hover:from-violet-500 hover:to-fuchsia-500 text-white font-semibold rounded-xl flex items-center justify-center gap-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <span>{t('startMagicSetup')}</span>
                  <ArrowRight className="w-4 h-4" />
                </button>

                <p className="text-center text-xs text-slate-500">
                  {t('linkedInPrivacy')}
                </p>
              </div>
            </div>
          )}

          {/* Step 2: Enriching */}
          {step === 'enriching' && (
            <div className="bg-slate-800/50 backdrop-blur border border-slate-700/50 rounded-2xl p-12 text-center">
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
                className="inline-block mb-6"
              >
                <Sparkles className="w-12 h-12 text-violet-400" />
              </motion.div>
              
              <h2 className="text-xl font-semibold text-white mb-2">
                {t('pleaseWait')}
              </h2>
              <p className="text-slate-400">
                {t('analyzingProfile')}
              </p>
              
              <div className="mt-8 space-y-2">
                {[
                  t('fetchingProfile'),
                  t('analyzingExperience'),
                  t('extractingSkills')
                ].map((task, i) => (
                  <motion.div
                    key={task}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: i * 0.5 }}
                    className="flex items-center justify-center gap-2 text-sm text-slate-400"
                  >
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>{task}</span>
                  </motion.div>
                ))}
              </div>
            </div>
          )}

          {/* Step 3: Chat */}
          {step === 'chat' && (
            <ProfileChat
              profileType="sales"
              initialData={linkedinData}
              userName={userName}
              onComplete={handleProfileComplete}
            />
          )}

          {/* Step 4: Complete */}
          {step === 'complete' && (
            <div className="bg-slate-800/50 backdrop-blur border border-slate-700/50 rounded-2xl p-12 text-center">
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ type: 'spring', duration: 0.5 }}
                className="inline-flex p-4 rounded-full bg-emerald-500/20 mb-6"
              >
                <CheckCircle2 className="w-12 h-12 text-emerald-400" />
              </motion.div>
              
              <h2 className="text-2xl font-bold text-white mb-2">
                {t('profileSaved')} 🎉
              </h2>
              <p className="text-slate-400 mb-6">
                {t('redirecting')}
              </p>
              
              <Loader2 className="w-6 h-6 animate-spin text-violet-400 mx-auto" />
            </div>
          )}
        </motion.div>
      </div>
    </div>
  );
}

