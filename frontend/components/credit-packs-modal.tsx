'use client'

import { useState, useEffect } from 'react'
import { Loader2, Zap, Star, Crown, Check, Plus, Package } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'
import { useToast } from '@/components/ui/use-toast'

interface CreditPack {
  id: string
  name: string
  credits: number
  price_cents: number
  per_credit_cents?: number
  description?: string
  popular?: boolean
  best_value?: boolean
}

interface CreditPacksModalProps {
  className?: string
  onSuccess?: () => void
  trigger?: React.ReactNode
}

export function CreditPacksModal({ className, onSuccess, trigger }: CreditPacksModalProps) {
  const { toast } = useToast()
  const [open, setOpen] = useState(false)
  const [packs, setPacks] = useState<CreditPack[]>([])
  const [loading, setLoading] = useState(true)
  const [purchasing, setPurchasing] = useState<string | null>(null)

  useEffect(() => {
    if (open) {
      fetchPacks()
    }
  }, [open])

  const fetchPacks = async () => {
    setLoading(true)
    try {
      const response = await api.get<CreditPack[]>('/api/v1/billing/flow-packs/products')
      if (response.data) {
        setPacks(response.data)
      }
    } catch (err) {
      console.error('Failed to load credit packs:', err)
    } finally {
      setLoading(false)
    }
  }

  const handlePurchase = async (packId: string) => {
    setPurchasing(packId)
    try {
      const response = await api.post<{ checkout_url: string }>('/api/v1/billing/flow-packs/checkout', {
        pack_id: packId,
        success_url: `${window.location.origin}/dashboard/settings?credits=success`,
        cancel_url: `${window.location.origin}/dashboard/settings?credits=cancelled`,
      })
      
      if (response.data?.checkout_url) {
        window.location.href = response.data.checkout_url
      } else {
        throw new Error('No checkout URL received')
      }
    } catch (err) {
      console.error('Purchase failed:', err)
      toast({
        title: 'Fout',
        description: 'Kon checkout niet starten. Probeer opnieuw.',
        variant: 'destructive',
      })
    } finally {
      setPurchasing(null)
    }
  }

  const formatPrice = (cents: number) => {
    return new Intl.NumberFormat('nl-NL', {
      style: 'currency',
      currency: 'EUR',
    }).format(cents / 100)
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {trigger || (
          <Button variant="outline" size="sm" className={cn("gap-2", className)}>
            <Plus className="h-4 w-4" />
            Credits Bijkopen
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Package className="h-5 w-5 text-emerald-500" />
            Credits Bijkopen
          </DialogTitle>
          <DialogDescription>
            Koop extra credits om door te gaan met je sales intelligence. Credits vervallen nooit.
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
          </div>
        ) : packs.length === 0 ? (
          <div className="text-center py-8 text-slate-500">
            Geen credit packs beschikbaar
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-3 py-4">
            {packs.map((pack) => (
              <div
                key={pack.id}
                className={cn(
                  "relative p-4 rounded-lg border-2 transition-all hover:shadow-md",
                  pack.popular ? "border-indigo-400 bg-indigo-50/50 dark:bg-indigo-950/20" :
                  pack.best_value ? "border-emerald-400 bg-emerald-50/50 dark:bg-emerald-950/20" :
                  "border-slate-200 dark:border-slate-700"
                )}
              >
                {pack.popular && (
                  <div className="absolute -top-2.5 left-1/2 -translate-x-1/2">
                    <Badge className="bg-indigo-500 text-white text-xs">
                      <Star className="h-3 w-3 mr-1" />
                      Populair
                    </Badge>
                  </div>
                )}
                {pack.best_value && (
                  <div className="absolute -top-2.5 left-1/2 -translate-x-1/2">
                    <Badge className="bg-emerald-500 text-white text-xs">
                      <Crown className="h-3 w-3 mr-1" />
                      Beste Deal
                    </Badge>
                  </div>
                )}

                <div className="text-center mb-3 pt-1">
                  <div className="flex items-center justify-center gap-1.5 mb-1">
                    <Zap className={cn(
                      "h-4 w-4",
                      pack.popular ? "text-indigo-500" :
                      pack.best_value ? "text-emerald-500" :
                      "text-amber-500"
                    )} />
                    <span className="font-semibold text-slate-900 dark:text-white">
                      {pack.name}
                    </span>
                  </div>
                  <p className="text-xs text-slate-500">
                    ~{Math.round(pack.credits / 30)} sales cycles
                  </p>
                </div>

                <div className="text-center mb-3">
                  <span className="text-2xl font-bold text-slate-900 dark:text-white">
                    {formatPrice(pack.price_cents)}
                  </span>
                  {pack.per_credit_cents && (
                    <p className="text-xs text-slate-400 mt-0.5">
                      {formatPrice(pack.per_credit_cents)} per credit
                    </p>
                  )}
                </div>

                <div className="space-y-1 mb-3 text-xs">
                  <div className="flex items-center gap-1.5 text-slate-600 dark:text-slate-400">
                    <Check className="h-3 w-3 text-emerald-500 flex-shrink-0" />
                    <span>{pack.credits} credits</span>
                  </div>
                  <div className="flex items-center gap-1.5 text-slate-600 dark:text-slate-400">
                    <Check className="h-3 w-3 text-emerald-500 flex-shrink-0" />
                    <span>Nooit verlopen</span>
                  </div>
                  <div className="flex items-center gap-1.5 text-slate-600 dark:text-slate-400">
                    <Check className="h-3 w-3 text-emerald-500 flex-shrink-0" />
                    <span>Direct beschikbaar</span>
                  </div>
                </div>

                <Button
                  size="sm"
                  className={cn(
                    "w-full",
                    pack.popular && "bg-indigo-600 hover:bg-indigo-700",
                    pack.best_value && "bg-emerald-600 hover:bg-emerald-700"
                  )}
                  onClick={() => handlePurchase(pack.id)}
                  disabled={purchasing !== null}
                >
                  {purchasing === pack.id ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin mr-2" />
                      Even geduld...
                    </>
                  ) : (
                    'Kopen'
                  )}
                </Button>
              </div>
            ))}
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}

