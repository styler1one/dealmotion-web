'use client'

import { useState, useEffect, useCallback } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useTranslations } from 'next-intl'
import { createClientComponentClient } from '@supabase/auth-helpers-nextjs'
import { User } from '@supabase/supabase-js'
import { 
  Target, 
  ArrowLeft,
  Loader2
} from 'lucide-react'
import { DashboardLayout } from '@/components/layout/dashboard-layout'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { useToast } from '@/components/ui/use-toast'
import { Prospect } from '@/types'

export default function NewDealPage() {
  const params = useParams()
  const router = useRouter()
  const prospectId = params.id as string
  const t = useTranslations('deals')
  const tCommon = useTranslations('common')
  const { toast } = useToast()
  
  const supabase = createClientComponentClient()
  const [user, setUser] = useState<User | null>(null)
  const [organizationId, setOrganizationId] = useState<string | null>(null)
  const [prospect, setProspect] = useState<Prospect | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  
  // Form state
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  
  // Fetch user, org, and prospect in one effect
  useEffect(() => {
    async function loadData() {
      try {
        const { data: { user } } = await supabase.auth.getUser()
        setUser(user)
        
        if (!user) {
          setLoading(false)
          return
        }
        
        // Get organization ID
        const { data: orgMember } = await supabase
          .from('organization_members')
          .select('organization_id')
          .eq('user_id', user.id)
          .single()
        
        if (!orgMember) {
          setLoading(false)
          return
        }
        
        setOrganizationId(orgMember.organization_id)
        
        // Fetch prospect
        const { data: prospectData } = await supabase
          .from('prospects')
          .select('*')
          .eq('id', prospectId)
          .eq('organization_id', orgMember.organization_id)
          .single()
        
        if (prospectData) {
          setProspect(prospectData)
        }
      } catch (error) {
        console.error('Error loading data:', error)
        toast({ variant: "destructive", title: t('errors.loadFailed') })
      } finally {
        setLoading(false)
      }
    }
    
    loadData()
  }, [prospectId, supabase, t, toast])
  
  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!name.trim()) {
      toast({ variant: "destructive", title: t('errors.nameRequired') })
      return
    }
    
    if (!user || !organizationId) {
      toast({ variant: "destructive", title: tCommon('errors.notLoggedIn') })
      return
    }
    
    setSaving(true)
    
    try {
      // Create deal using already loaded user and org
      const { data, error } = await supabase
        .from('deals')
        .insert({
          name: name.trim(),
          description: description.trim() || null,
          prospect_id: prospectId,
          organization_id: organizationId,
          created_by: user.id,
          is_active: true
        })
        .select()
        .single()
      
      if (error) {
        console.error('Error creating deal:', error)
        toast({ variant: "destructive", title: t('errors.createFailed') })
        return
      }
      
      toast({ title: t('success.created') })
      router.push(`/dashboard/prospects/${prospectId}/deals/${data.id}`)
      
    } catch (error) {
      console.error('Error creating deal:', error)
      toast({ variant: "destructive", title: t('errors.createFailed') })
    } finally {
      setSaving(false)
    }
  }, [name, description, user, organizationId, prospectId, supabase, router, t, tCommon, toast])
  
  if (loading) {
    return (
      <DashboardLayout user={user}>
        <div className="flex items-center justify-center h-96">
          <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
        </div>
      </DashboardLayout>
    )
  }
  
  return (
    <DashboardLayout user={user}>
      <div className="max-w-2xl mx-auto space-y-6">
        {/* Back Button */}
        <Button 
          variant="ghost" 
          onClick={() => router.back()}
          className="mb-4"
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          {tCommon('back')}
        </Button>
        
        {/* Form Card */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-purple-500 to-purple-600 flex items-center justify-center">
                <Target className="w-5 h-5 text-white" />
              </div>
              <div>
                <CardTitle>{t('new.title')}</CardTitle>
                <CardDescription>
                  {prospect?.company_name && (
                    <span>{t('new.for')} <strong>{prospect.company_name}</strong></span>
                  )}
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-6">
              {/* Deal Name */}
              <div className="space-y-2">
                <Label htmlFor="name">{t('form.name')}</Label>
                <Input
                  id="name"
                  placeholder={t('form.namePlaceholder')}
                  value={name}
                  onChange={e => setName(e.target.value)}
                  required
                />
                <p className="text-xs text-slate-500">
                  {t('form.nameHelp')}
                </p>
              </div>
              
              {/* Description */}
              <div className="space-y-2">
                <Label htmlFor="description">{t('form.description')}</Label>
                <Textarea
                  id="description"
                  placeholder={t('form.descriptionPlaceholder')}
                  value={description}
                  onChange={e => setDescription(e.target.value)}
                  rows={4}
                />
                <p className="text-xs text-slate-500">
                  {t('form.descriptionHelp')}
                </p>
              </div>
              
              {/* Info Box */}
              <div className="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg text-sm">
                <p className="text-blue-700 dark:text-blue-300">
                  💡 {t('new.info')}
                </p>
              </div>
              
              {/* Submit */}
              <div className="flex gap-3">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => router.back()}
                >
                  {tCommon('cancel')}
                </Button>
                <Button type="submit" disabled={saving}>
                  {saving ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      {tCommon('saving')}
                    </>
                  ) : (
                    <>
                      <Target className="w-4 h-4 mr-2" />
                      {t('new.create')}
                    </>
                  )}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  )
}
