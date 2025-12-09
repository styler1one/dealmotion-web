'use client'

import { createContext, useContext, ReactNode } from 'react'

export type AdminRole = 'super_admin' | 'admin' | 'support' | 'viewer'

interface AdminContextType {
  role: AdminRole
  isSuperAdmin: boolean
  isAdmin: boolean
  isSupport: boolean
  canManageUsers: boolean
  canManageAdmins: boolean
  canViewBilling: boolean
  canModifyData: boolean
}

const AdminContext = createContext<AdminContextType | null>(null)

interface AdminProviderProps {
  children: ReactNode
  role: AdminRole
}

export function AdminProvider({ children, role }: AdminProviderProps) {
  const value: AdminContextType = {
    role,
    isSuperAdmin: role === 'super_admin',
    isAdmin: role === 'super_admin' || role === 'admin',
    isSupport: role === 'super_admin' || role === 'admin' || role === 'support',
    canManageUsers: role === 'super_admin' || role === 'admin' || role === 'support',
    canManageAdmins: role === 'super_admin',
    canViewBilling: role === 'super_admin' || role === 'admin',
    canModifyData: role !== 'viewer',
  }

  return (
    <AdminContext.Provider value={value}>
      {children}
    </AdminContext.Provider>
  )
}

export function useAdmin() {
  const context = useContext(AdminContext)
  if (!context) {
    throw new Error('useAdmin must be used within AdminProvider')
  }
  return context
}

export function useAdminRole() {
  const { role } = useAdmin()
  return role
}

