'use client'

import { useState, useEffect, useCallback } from 'react'
import { createClientComponentClient } from '@supabase/auth-helpers-nextjs'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Icons } from '@/components/icons'
import { FileUploadZone } from '@/components/knowledge-base/file-upload-zone'
import { FileList } from '@/components/knowledge-base/file-list'
import { useToast } from '@/components/ui/use-toast'
import { Toaster } from '@/components/ui/toaster'
import { DashboardLayout } from '@/components/layout'
import { useTranslations } from 'next-intl'
import type { User } from '@supabase/supabase-js'

interface KnowledgeBaseFile {
  id: string
  filename: string
  file_size: number
  file_type: string
  status: 'uploading' | 'processing' | 'completed' | 'failed'
  chunk_count: number
  error_message?: string
  created_at: string
  processed_at?: string
}

export default function KnowledgeBasePage() {
  const router = useRouter()
  const supabase = createClientComponentClient()
  const { toast } = useToast()
  const t = useTranslations('knowledgeBase')
  const tCommon = useTranslations('common')
  const [user, setUser] = useState<User | null>(null)
  const [files, setFiles] = useState<KnowledgeBaseFile[]>([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)

  useEffect(() => {
    const getUser = async () => {
      const { data: { user } } = await supabase.auth.getUser()
      setUser(user)
      if (user) {
        fetchFiles()
      }
      setLoading(false)
    }
    getUser()
  }, [supabase])

  const fetchFiles = useCallback(async () => {
    try {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) return

      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/knowledge-base/files`,
        {
          headers: {
            'Authorization': `Bearer ${session.access_token}`
          }
        }
      )

      if (response.ok) {
        const data = await response.json()
        setFiles(data.files || [])
      }
    } catch (error) {
      console.error('Failed to fetch files:', error)
    }
  }, [supabase])

  const handleFileUpload = async (file: File) => {
    setUploading(true)
    try {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) {
        throw new Error('Not authenticated')
      }

      const formData = new FormData()
      formData.append('file', file)

      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      
      const response = await fetch(
        `${apiUrl}/api/v1/knowledge-base/upload`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${session.access_token}`
          },
          body: formData
        }
      )

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Upload failed')
      }

      // Refresh file list
      await fetchFiles()
      
      toast({
        title: t('toast.uploaded'),
        description: t('toast.uploadedDesc'),
      })
      
      // Start polling for status updates
      setTimeout(() => fetchFiles(), 2000)
    } catch (error) {
      console.error('Upload failed:', error)
      toast({
        variant: "destructive",
        title: t('toast.failed'),
        description: t('toast.failedDesc'),
      })
    } finally {
      setUploading(false)
    }
  }

  const handleDeleteFile = async (fileId: string) => {
    try {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) return

      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/knowledge-base/files/${fileId}`,
        {
          method: 'DELETE',
          headers: {
            'Authorization': `Bearer ${session.access_token}`
          }
        }
      )

      if (response.ok) {
        await fetchFiles()
        toast({
          title: t('toast.deleted'),
          description: t('toast.deletedDesc'),
        })
      } else {
        throw new Error('Delete failed')
      }
    } catch (error) {
      console.error('Delete failed:', error)
      toast({
        variant: "destructive",
        title: t('toast.deleteFailed'),
        description: t('toast.deleteFailedDesc'),
      })
    }
  }

  const handleSignOut = async () => {
    await supabase.auth.signOut()
    router.push('/login')
  }

  // Auto-refresh for processing files
  useEffect(() => {
    const hasProcessingFiles = files.some(f => 
      f.status === 'uploading' || f.status === 'processing'
    )

    if (hasProcessingFiles) {
      const interval = setInterval(() => {
        fetchFiles()
      }, 3000) // Poll every 3 seconds

      return () => clearInterval(interval)
    }
  }, [files, fetchFiles])

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-slate-50 dark:bg-slate-900">
        <div className="text-center space-y-4">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="text-slate-600 dark:text-slate-400">{t('loading')}</p>
        </div>
      </div>
    )
  }

  if (!user) {
    router.push('/login')
    return null
  }

  const completedFiles = files.filter(f => f.status === 'completed').length
  const processingFiles = files.filter(f => f.status === 'processing' || f.status === 'uploading').length
  const failedFiles = files.filter(f => f.status === 'failed').length

  return (
    <DashboardLayout user={user}>
      <div className="p-6 lg:p-8 max-w-6xl mx-auto animate-fade-in">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl lg:text-3xl font-bold text-slate-900 dark:text-white mb-2">
            {t('title')}
          </h1>
          <p className="text-slate-500 dark:text-slate-400">
            {t('subtitle')}
          </p>
        </div>

        {/* Stats */}
        <div className="grid gap-4 md:grid-cols-3 mb-8">
          <div className="group rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 shadow-sm hover:shadow-lg transition-all">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-slate-600 dark:text-slate-400 mb-1">
                  {t('stats.completed')}
                </p>
                <p className="text-3xl font-bold text-green-600 dark:text-green-400">{completedFiles}</p>
              </div>
              <div className="h-14 w-14 rounded-full bg-green-50 dark:bg-green-900/20 flex items-center justify-center group-hover:scale-110 transition-transform">
                <Icons.checkCircle className="h-7 w-7 text-green-600 dark:text-green-400" />
              </div>
            </div>
          </div>

          <div className="group rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 shadow-sm hover:shadow-lg transition-all">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-slate-600 dark:text-slate-400 mb-1">
                  Processing
                </p>
                <p className="text-3xl font-bold text-blue-600 dark:text-blue-400">{processingFiles}</p>
              </div>
              <div className="h-14 w-14 rounded-full bg-blue-50 dark:bg-blue-900/20 flex items-center justify-center">
                <Icons.spinner className="h-7 w-7 text-blue-600 dark:text-blue-400 animate-spin" />
              </div>
            </div>
          </div>

          <div className="group rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 shadow-sm hover:shadow-lg transition-all">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-slate-600 dark:text-slate-400 mb-1">
                  Failed
                </p>
                <p className="text-3xl font-bold text-red-600 dark:text-red-400">{failedFiles}</p>
              </div>
              <div className="h-14 w-14 rounded-full bg-red-50 dark:bg-red-900/20 flex items-center justify-center group-hover:scale-110 transition-transform">
                <Icons.alertCircle className="h-7 w-7 text-red-600 dark:text-red-400" />
              </div>
            </div>
          </div>
        </div>

        {/* Upload Zone */}
        <FileUploadZone 
          onUpload={handleFileUpload}
          uploading={uploading}
        />

        {/* File List */}
        <div className="mt-8">
          <FileList 
            files={files}
            onDelete={handleDeleteFile}
            onRefresh={fetchFiles}
          />
        </div>
        
        <Toaster />
      </div>
    </DashboardLayout>
  )
}
