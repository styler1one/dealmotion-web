# 🔄 Ways of Working - DealMotion

**Versie**: 3.5  
**Laatst bijgewerkt**: 9 December 2025

> ⚠️ **Bij elke sessie**: Update de "Handover & Huidige Status" sectie aan het eind!

Dit document beschrijft HOE we werken aan DealMotion. Volg deze processen voor consistentie en traceerbaarheid.

---

## 🔄 Handover & Huidige Status

### Start Nieuwe Chat

Bij het starten van een nieuwe chat, stuur dit bericht (afhankelijk van welke workspace je open hebt):

**Voor dealmotion-web (frontend + backend):**
```
Ik wil verder werken aan DealMotion Web.

**Stap 1 - Project Context:**
Lees @WAYS_OF_WORKING.md voor huidige status en werkwijze.

**Stap 2 - Data Model:**
Lees @backend/database/complete_schema.sql voor de database structuur.

**Stap 3 - Code Architectuur:**
List deze folders om de app structuur te begrijpen:
- backend/app (routers, services, models)
- frontend/app (pages en routes)
- frontend/components (UI componenten)

Na het lezen: Vat kort samen wat de huidige status is en bevestig dat je de app structuur begrijpt. Wacht dan op mijn instructies.
```

**Voor dealmotion-mobile (Flutter app):**
```
Ik wil verder werken aan DealMotion Mobile.

**Stap 1 - Project Context:**
Lees @WAYS_OF_WORKING.md (in dealmotion-docs) voor huidige status.

**Stap 2 - Code Architectuur:**
List deze folders:
- lib/core (config, routing, theme)
- lib/features (auth, home, meetings, recording, research, preparation, prospects)
- lib/shared (widgets, services)

Na het lezen: Vat kort samen wat de huidige status is. Wacht dan op mijn instructies.
```

De AI zal dan:
1. WAYS_OF_WORKING lezen → huidige status, werkwijze, handover context
2. Database/Code structuur lezen → relevante architectuur
3. Samenvatten wat begrepen is → bevestigt volledige context

### 📍 Huidige Status

| Item | Status |
|------|--------|
| **Huidige Fase** | Production Ready + Mobile App 82% Complete |
| **Focus** | SPEC-040: Mobile App (Phase 5: Push Notifications) |
| **Blokkeerders** | Geen |
| **Laatst Gedeployed** | 9 December 2025 |

### ✅ Recent Afgerond (laatste 5)

1. **📱 SPEC-040: Mobile App Phase 1-4 Complete** - Alle MUST features werkend (9 Dec) ✅
   - Bottom Navigation (5 tabs) + Quick Actions Sheet
   - Home Dashboard met live stats
   - Meetings Screen met calendar data
   - Research Create + Preparation Create flows (API fix)
   - Document Viewers (Research, Prep, Followup)
   - Prospect Hub met Notes (add/pin/delete)
   - **Code Quality**: 0 errors, 0 warnings, 30 info hints
   - **TODO**: Push notifications, Offline caching, App Store submission
2. **🖥️ SPEC-038 Phase 4: Microsoft 365 + Teams** - Volledige integratie werkend (8 Dec) ✅
   - Microsoft 365 Calendar OAuth flow
   - Calendar sync met Microsoft Graph API
   - Teams recordings & transcripts import
3. **🔥 SPEC-038 Phase 3: Fireflies Integration** - Volledige integratie werkend (8 Dec) ✅
   - API key connection met Fernet encryption
   - Auto-sync elke 5 minuten (Inngest cron)
   - Import Modal met prospect/contact/prep linking
4. **📅 SPEC-038 Phase 1: Meetings & Calendar Integration** - Google Calendar volledig werkend (7 Dec) ✅
   - 19 sprints voltooid
   - Google Calendar OAuth flow (connect/disconnect)
   - Calendar sync service met 15-min auto-refresh (Inngest)
5. **🔧 Frontend Code Quality Review** - TypeScript & accessibility verbeteringen (6 Dec) ✅

### 📋 Volgende Stappen

1. **SPEC-040 Phase 5: Push Notifications** - Firebase Cloud Messaging
   - Firebase project setup
   - FCM token registration
   - Permission request flow
   - Deep link routing from notifications
2. **SPEC-040 Phase 5.2: Offline Caching** - Hive caching
   - Meetings cache
   - Prospects cache
   - Documents cache
   - Sync on app open
3. **SPEC-040 Phase 6: App Store Release** - Submit naar App Store & Play Store
   - App Store assets
   - Play Store assets
   - TestFlight beta
4. **SPEC-038 Phase 4.5-4.7: Browser Recording** - Opnemen in de browser (optional)
5. **Beta launch** - Eerste beta users uitnodigen

### 📚 Belangrijke Documenten voor Context

**Primair (altijd lezen bij handover):**

| Document | Wat je er vindt |
|----------|-----------------|
| `WAYS_OF_WORKING.md` | Dit document - huidige status, werkwijze, handover info |
| `DEV_MASTER_PLAN.md` | Volledige roadmap, alle phases, huidige prioriteiten |
| `CHANGELOG.md` | Alle releases en wijzigingen |

**Recente Taken:**

| Document | Wat je er vindt |
|----------|-----------------|
| `tasks/TASK-045-Mobile-App.md` | Mobile App uitbreiding (Phase 1-4 ✅, Phase 5 pending) |
| `tasks/TASK-044-Meetings-Calendar-Integration.md` | Calendar & Mobile App implementatie (Phase 1 ✅) |
| `tasks/TASK-042-Admin-Panel.md` | Admin Panel implementatie (FASE 1-8 done) ✅ |
| `tasks/TASK-041-Dashboard-Mission-Control.md` | Dashboard redesign "Mission Control" ✅ |
| `TECH_DEBT_REGISTER.md` | Open technical debt items |

**Specificaties (raadplegen indien nodig):**

| Document | Wat je er vindt |
|----------|-----------------|
| `specs/SPEC-040-Mobile-App.md` | Mobile App uitbreiding (Phase 1-4 ✅, Phase 5-6 pending) |
| `specs/SPEC-038-Meetings-Calendar-Integration.md` | Meetings & Calendar + Mobile Recording App (Phase 1 ✅) |
| `specs/SPEC-037-Admin-Panel.md` | Admin Panel specificatie ✅ |
| `specs/SPEC-036-Dashboard-Mission-Control.md` | Dashboard "Mission Control" redesign ✅ |
| `specs/SPEC-035-Prospect-Hub-Guided-Journey.md` | Prospect Hub design specs ✅ |
| `specs/SPEC-022-Subscription-Billing.md` | Billing v2/v3 pricing specs |
| `PRODUCT_DOCS_INDEX.md` | Index van alle specs/tasks |

**Optioneel (voor context):**

| Document | Wat je er vindt |
|----------|-----------------|
| `PRODUCT_IDEAS.md` | Feature backlog & brainstorm ideeën |
| `RISK_REGISTER.md` | Project risico's en mitigaties |
| `PRODUCT_OWNER_ANALYSIS.md` | Product health check (maandelijks) |

### ⚠️ Bekende Aandachtspunten

- **Email**: Inbox nodig voor `support@dealmotion.ai` en `sales@dealmotion.ai`
- **Stripe**: Flow Pack product moet nog worden aangemaakt in Stripe dashboard
- **Flow Refund**: Bij delete research wordt flow nog niet teruggeteld

### 🧠 Context voor AI Assistant

**Development regels:**
- English-First voor i18n (alleen `en.json` tijdens dev, andere talen in batch)
- Geen lokale installaties - alleen cloud development
- Commit altijd via git met conventionele messages
- Update documentatie na elke significante wijziging

**Code locaties (nieuwe multi-repo structuur):**
- Web Frontend: `C:\Cursor\dealmotion-web\frontend\` → GitHub: `dealmotion-web`
- Web Backend: `C:\Cursor\dealmotion-web\backend\` → GitHub: `dealmotion-web`
- Mobile App: `C:\Cursor\dealmotion-mobile\` → GitHub: `dealmotion-mobile`
- Documentation: `C:\Cursor\dealmotion-docs\` → GitHub: `dealmotion-docs` (private)

---

## 🏢 Project Info

### Applicatie

| Item | Waarde |
|------|--------|
| **Naam** | DealMotion |
| **Beschrijving** | AI-powered sales enablement - Put your deals in motion |
| **Frontend URL** | https://dealmotion.ai |
| **Backend URL** | https://api.dealmotion.ai |
| **Status** | 🟢 Production Ready (Stripe live) |

### Platformen & Services

| Platform | Doel | URL | Account |
|----------|------|-----|---------|
| **GitHub (Web)** | Frontend + Backend | https://github.com/styler1one/dealmotion-web | styler1one |
| **GitHub (Mobile)** | Flutter App | https://github.com/styler1one/dealmotion-mobile | styler1one |
| **GitHub (Docs)** | Documentation | https://github.com/styler1one/dealmotion-docs | styler1one |
| **Vercel** | Frontend hosting | https://vercel.com | - |
| **Railway** | Backend hosting | https://railway.app | - |
| **Supabase** | Database & Auth | https://supabase.com | - |
| **Stripe** | Betalingen | https://dashboard.stripe.com | - |
| **Inngest** | Workflow orchestration | https://app.inngest.com | - |
| **Pinecone** | Vector database | https://app.pinecone.io | - |
| **Deepgram** | Audio transcriptie | https://console.deepgram.com | - |

### API Keys & Secrets

⚠️ **Alle secrets staan in:**
- Vercel: Project Settings → Environment Variables
- Railway: Project Settings → Variables

---

## 🚀 Deployment & Release

### Automatische Deployment

```
┌─────────────────────────────────────────────────────────────────┐
│  git push origin main                                           │
├─────────────────────────────────────────────────────────────────┤
│  ↓ Automatisch:                                                 │
│  • Vercel detecteert push → bouwt & deployed frontend           │
│  • Railway detecteert push → bouwt & deployed backend           │
│  • Geen handmatige actie nodig                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Release Workflow

```bash
# 1. Maak wijzigingen
git add -A

# 2. Commit met conventionele message
git commit -m "feat: add new feature"

# 3. Push naar main (triggert auto-deploy)
git push origin main

# 4. Check deployments
#    - Vercel: https://vercel.com/[project]/deployments
#    - Railway: https://railway.app/project/[id]
```

### Branch Strategie

| Branch | Doel | Auto-deploy naar |
|--------|------|------------------|
| `main` | Production | Vercel + Railway (production) |
| `staging` | Staging tests | (niet geconfigureerd) |
| `feature/*` | Feature development | (geen deploy) |

### Rollback

Bij problemen na deploy:
```bash
# Via Vercel dashboard: "Instant Rollback" knop
# Of via git:
git revert HEAD
git push origin main
```

---

## 📋 Document Overzicht

| Document | Doel | Wanneer Updaten |
|----------|------|-----------------|
| `DEV_MASTER_PLAN.md` | Roadmap & Phases | Bij nieuwe phase/feature |
| `CHANGELOG.md` | Release notes | Na elke release |
| `TECH_DEBT_REGISTER.md` | Tech schuld tracking | Bij ontdekking/fix |
| `RISK_REGISTER.md` | Risico management | Maandelijks + bij nieuwe risico's |
| `PRODUCT_OWNER_ANALYSIS.md` | Health check | Maandelijks |
| `COMPETITOR_ANALYSIS_*.md` | Markt research | Kwartaal |
| `specs/SPEC-XXX.md` | Feature specs | Vóór development |
| `tasks/TASK-XXX.md` | Implementation tasks | Bij start development |

---

## 🚀 Workflow: Nieuwe Feature

```
┌─────────────────────────────────────────────────────────────────┐
│  FASE 1: IDEE & PLANNING                                        │
├─────────────────────────────────────────────────────────────────┤
│  1. Log idee in COMPETITOR_ANALYSIS of DEV_MASTER_PLAN          │
│  2. Prioriteer (P0/P1/P2/P3)                                    │
│  3. Schat effort (S/M/L/XL)                                     │
│  4. Besluit: Build / Postpone / Cancel                          │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  FASE 2: SPECIFICATIE                                           │
├─────────────────────────────────────────────────────────────────┤
│  1. Maak specs/SPEC-XXX-[Feature].md                            │
│  2. Beschrijf: User Stories, API, Database, UI                  │
│  3. Review & approve specificatie                               │
│  4. Update DEV_MASTER_PLAN met nieuwe Phase                     │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  FASE 3: DEVELOPMENT                                            │
├─────────────────────────────────────────────────────────────────┤
│  1. Maak tasks/TASK-XXX-[Feature].md                            │
│  2. Break down in subtasks                                      │
│  3. Bouw feature (backend → frontend)                           │
│  4. Test lokaal                                                 │
│  5. Commit met duidelijke message                               │
│  6. Push naar GitHub                                            │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  FASE 4: DEPLOYMENT & DOCS                                      │
├─────────────────────────────────────────────────────────────────┤
│  1. Deploy naar staging (automatisch via Vercel/Railway)        │
│  2. Test op staging                                             │
│  3. Deploy naar production                                      │
│  4. Update CHANGELOG.md                                         │
│  5. Update DEV_MASTER_PLAN (mark as ✅ Completed)               │
│  6. Update TASK als ✅ Completed                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🐛 Workflow: Bug Fix

```
┌─────────────────────────────────────────────────────────────────┐
│  1. IDENTIFY                                                    │
│     └─ Log bug in PRODUCT_OWNER_ANALYSIS.md (Bekende Issues)    │
│     └─ Bepaal severity: Critical / High / Medium / Low          │
├─────────────────────────────────────────────────────────────────┤
│  2. FIX                                                         │
│     └─ Geen aparte SPEC nodig voor bugs                         │
│     └─ Fix in code                                              │
│     └─ Commit: "fix: [description]"                             │
├─────────────────────────────────────────────────────────────────┤
│  3. DEPLOY & DOCUMENT                                           │
│     └─ Deploy                                                   │
│     └─ Update CHANGELOG.md                                      │
│     └─ Remove from PRODUCT_OWNER_ANALYSIS (of mark resolved)    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔧 Workflow: Tech Debt

```
┌─────────────────────────────────────────────────────────────────┐
│  1. ONTDEKKEN                                                   │
│     └─ Log in TECH_DEBT_REGISTER.md                             │
│     └─ Assign TD-XXX nummer                                     │
│     └─ Bepaal priority: Critical / High / Medium / Low          │
│     └─ Schat effort                                             │
├─────────────────────────────────────────────────────────────────┤
│  2. PLANNEN                                                     │
│     └─ Critical: Fix in huidige sprint                          │
│     └─ High: Plan voor volgende sprint                          │
│     └─ Medium/Low: Backlog, pak op bij gelegenheid              │
├─────────────────────────────────────────────────────────────────┤
│  3. FIXEN                                                       │
│     └─ Fix de tech debt                                         │
│     └─ Commit: "refactor: [TD-XXX] description"                 │
│     └─ Update TECH_DEBT_REGISTER (mark resolved)                │
│     └─ Update summary counts                                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔍 Workflow: Code Quality Check

Periodieke code review om technische kwaliteit te waarborgen.

```
┌─────────────────────────────────────────────────────────────────┐
│  WANNEER: Na elke major feature of maandelijks                  │
├─────────────────────────────────────────────────────────────────┤
│  SCOPE: Identificeer verbeterpunten in:                         │
│  - Code duplicatie                                              │
│  - Type safety (TypeScript)                                     │
│  - Error handling                                               │
│  - Accessibility (a11y)                                         │
│  - Performance                                                  │
│  - Security                                                     │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  FASE 1: ANALYSE                                                │
├─────────────────────────────────────────────────────────────────┤
│  1. Review codebase op patterns en anti-patterns                │
│  2. Check voor herhaalde code (DRY principe)                    │
│  3. Identificeer ontbrekende utilities                          │
│  4. Check TypeScript `any` types                                │
│  5. Review error handling consistentie                          │
│  6. Check accessibility compliance                              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  FASE 2: PLANNING                                               │
├─────────────────────────────────────────────────────────────────┤
│  1. Prioriteer verbeteringen (impact vs effort)                 │
│  2. Groepeer in logische fases                                  │
│  3. Schat tijd per fase                                         │
│  4. Log grote items in TECH_DEBT_REGISTER.md indien nodig       │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  FASE 3: IMPLEMENTATIE                                          │
├─────────────────────────────────────────────────────────────────┤
│  1. Maak reusable utilities/hooks/components                    │
│  2. Test dat build slaagt na elke fase                          │
│  3. Commit per fase met duidelijke message:                     │
│     └─ "feat: add [utility] for [purpose]"                      │
│     └─ "refactor: centralize [pattern]"                         │
│  4. Push naar GitHub                                            │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  FASE 4: DOCUMENTATIE                                           │
├─────────────────────────────────────────────────────────────────┤
│  1. Update CHANGELOG.md met alle verbeteringen                  │
│  2. Update DEV_MASTER_PLAN.md                                   │
│  3. Update dit document indien process verbeterd                │
└─────────────────────────────────────────────────────────────────┘
```

### Code Quality Checklist

#### Frontend
- [ ] **Utilities**: Zijn er herbruikbare functies die ontbreken?
  - API client, validation, formatting, date/time, storage
- [ ] **Hooks**: Zijn er custom hooks nodig?
  - Data fetching, auth, keyboard, accessibility
- [ ] **Components**: Zijn er herbruikbare componenten nodig?
  - Error boundary, skeletons, empty states, status badges
- [ ] **Types**: Zijn er `any` types die vervangen moeten worden?
- [ ] **Error Handling**: Is error handling consistent?
- [ ] **Accessibility**: Zijn a11y utilities aanwezig?

#### Backend
- [ ] **Database**: Is database access gecentraliseerd?
- [ ] **Services**: Zijn services goed georganiseerd?
- [ ] **Validation**: Is input validatie consistent?
- [ ] **Logging**: Is logging gestructureerd?
- [ ] **Error Handling**: Zijn errors consistent geformatteerd?

### Beschikbare Utilities (Referentie)

Na code quality reviews zijn de volgende utilities beschikbaar:

| Categorie | Location | Functies |
|-----------|----------|----------|
| **API** | `lib/api.ts` | `apiClient`, `uploadFile` |
| **Auth** | `hooks/useAuth.ts` | `useAuth`, `useRequireAuth` |
| **Data Fetching** | `hooks/useFetch.ts` | `useFetch`, `useMutation`, `usePolling` |
| **Keyboard** | `hooks/useKeyboard.ts` | `useKeyboardShortcut`, `useFocusTrap`, `useHotkeys` |
| **Validation** | `lib/validation.ts` | `required`, `email`, `url`, `validateForm` |
| **Date/Time** | `lib/date-utils.ts` | `formatDate`, `getRelativeTime`, `smartDate` |
| **Formatting** | `lib/format-utils.ts` | `formatNumber`, `formatCurrency`, `truncate` |
| **Storage** | `lib/storage.ts` | `useLocalStorage`, `setCache`, `saveDraft` |
| **Async** | `lib/async-utils.ts` | `debounce`, `throttle`, `retry`, `poll` |
| **Clipboard** | `lib/clipboard.ts` | `copyToClipboard`, `useCopy` |
| **Accessibility** | `lib/accessibility.ts` | `announce`, `createFocusTrap`, `saveFocus` |
| **Constants** | `lib/constants.ts` | `API_ENDPOINTS`, `SUPPORTED_LOCALES` |
| **Activity** | `lib/constants/activity.ts` | `ACTIVITY_ICONS`, `getProspectStatusColor`, `MEETING_STATUS_COLORS` |
| **Export** | `lib/export-utils.ts` | `exportAsMarkdown`, `exportAsPdf`, `exportAsDocx` |

### Backend Import Patterns (Referentie)

⚠️ **LET OP**: Gebruik ALTIJD deze imports in backend routers:

```python
# ✅ GOED - Correct imports
from app.deps import get_current_user
from app.database import get_supabase_service

# ❌ FOUT - Deze module bestaat NIET
from app.dependencies import get_current_user, get_supabase_service
```

| Functie | Juiste Import | Doel |
|---------|---------------|------|
| `get_current_user` | `from app.deps import get_current_user` | Auth dependency voor routes |
| `get_supabase_service` | `from app.database import get_supabase_service` | Service role client (bypasses RLS) |
| `get_user_client` | `from app.database import get_user_client` | User-scoped client (uses JWT) |

### User ID van JWT Token

⚠️ **LET OP**: De JWT token gebruikt `sub` (subject) voor de user ID:

```python
# ✅ GOED
user_id = current_user["sub"]

# ❌ FOUT - KeyError!
user_id = current_user["id"]
```

### Backend Router Template

```python
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from app.deps import get_current_user
from app.database import get_supabase_service
from app.models.users import User

router = APIRouter(prefix="/example", tags=["example"])

@router.get("/items")
async def get_items(
    current_user: User = Depends(get_current_user)
):
    supabase = get_supabase_service()
    # ... implementation
```

### Naming Conventions (Entiteiten)

⚠️ **LET OP**: De term "company" wordt op twee verschillende manieren gebruikt:

| Term | Context | Beschrijving | Files |
|------|---------|--------------|-------|
| **company_profile** | Seller | Het bedrijf van de gebruiker (verkoper) | `company_profile.py`, `company_interview_service.py` |
| **company_lookup** | Prospect | Opzoeken van prospect bedrijf | `company_lookup.py` |
| **prospect** | Prospect | Het bedrijf dat onderzocht wordt voor verkoop | `prospect_*.py`, `research.py` |
| **contact** | Prospect | Een persoon bij het prospect bedrijf | `contact_*.py` |
| **seller_context** | Seller | Gecombineerde context van seller + company profile | `seller_context_builder.py` |

```
┌─────────────────────────────────────────────────────────────────┐
│  SELLER (Gebruiker van de app)                                  │
│  ├── sales_profile      → Persoonlijk profiel van verkoper      │
│  └── company_profile    → Bedrijf van de verkoper               │
├─────────────────────────────────────────────────────────────────┤
│  PROSPECT (Doelwit voor verkoop)                                │
│  ├── research_brief     → Research over prospect bedrijf        │
│  ├── company_lookup     → URL/LinkedIn lookup van prospect      │
│  └── contacts           → Personen bij het prospect bedrijf     │
└─────────────────────────────────────────────────────────────────┘
```

**Toekomstige verbetering** (TD-item): Refactor naming naar `seller_company_profile` en `prospect_lookup` voor meer duidelijkheid.

---

## 🌍 Workflow: Internationalization (i18n)

### Development Strategy: English-First

**Principe**: Bouw nieuwe features alleen met Engelse vertalingen. Andere talen worden in een batch aan het eind bijgewerkt.

```
┌─────────────────────────────────────────────────────────────────┐
│  TIJDENS DEVELOPMENT                                            │
├─────────────────────────────────────────────────────────────────┤
│  ✅ Gebruik useTranslations() hooks                             │
│  ✅ Voeg keys toe aan messages/en.json                          │
│  ✅ Behoud namespace structuur (deals, prospects, etc.)         │
│  ❌ SKIP: NL, DE, FR, ES, HI, AR vertalingen                    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  BATCH VERTALING (aan het eind van sprint/release)              │
├─────────────────────────────────────────────────────────────────┤
│  1. Identificeer alle nieuwe keys in messages/en.json           │
│  2. Vertaal naar alle 6 andere talen in één keer                │
│  3. Review vertalingen op consistentie                          │
│  4. Commit: "i18n: Add translations for [feature]"              │
└─────────────────────────────────────────────────────────────────┘
```

### Voordelen van English-First

| Aspect | Zonder English-First | Met English-First |
|--------|---------------------|-------------------|
| Tijd per feature | +30 min (7 talen) | +5 min (1 taal) |
| Context switches | Veel | Minimaal |
| Vertaal consistentie | Verspreid | Gecentraliseerd |
| Merge conflicts | Meer | Minder |

### i18n Architectuur (behouden)

```
frontend/
├── messages/
│   ├── en.json     ← Altijd updaten tijdens dev
│   ├── nl.json     ← Batch update aan het eind
│   ├── de.json     ← Batch update aan het eind
│   ├── fr.json     ← Batch update aan het eind
│   ├── es.json     ← Batch update aan het eind
│   ├── hi.json     ← Batch update aan het eind
│   └── ar.json     ← Batch update aan het eind
└── i18n/
    └── request.ts  ← Routing config (niet aanpassen)
```

### Voorbeeld: Nieuwe Feature

```tsx
// ✅ GOED: Gebruik i18n hooks
const t = useTranslations('newFeature');
return <h1>{t('title')}</h1>;

// ❌ FOUT: Hardcoded strings
return <h1>New Feature Title</h1>;
```

```json
// messages/en.json - WEL toevoegen
{
  "newFeature": {
    "title": "New Feature Title"
  }
}

// messages/nl.json - NIET toevoegen (later in batch)
```

---

## ⚠️ Workflow: Risk Management

```
┌─────────────────────────────────────────────────────────────────┐
│  MAANDELIJKSE REVIEW                                            │
├─────────────────────────────────────────────────────────────────┤
│  1. Open RISK_REGISTER.md                                       │
│  2. Review alle open risico's                                   │
│  3. Update status (Open/Monitoring/Mitigated/Closed)            │
│  4. Check mitigation progress                                   │
│  5. Identificeer nieuwe risico's                                │
│  6. Update "Review Date" voor elk risico                        │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  NIEUW RISICO ONTDEKT                                           │
├─────────────────────────────────────────────────────────────────┤
│  1. Log in RISK_REGISTER.md                                     │
│  2. Assign RISK-XXX nummer                                      │
│  3. Bepaal Probability × Impact                                 │
│  4. Beschrijf mitigation strategie                              │
│  5. Assign owner                                                │
│  6. Set review date                                             │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📝 Commit Message Convention

```
type(scope): subject

[optional body]

[optional footer]
```

### Types
| Type | Wanneer |
|------|---------|
| `feat` | Nieuwe feature |
| `fix` | Bug fix |
| `docs` | Documentatie |
| `style` | Formatting (geen code change) |
| `refactor` | Code refactoring |
| `test` | Tests toevoegen |
| `chore` | Maintenance, dependencies |
| `i18n` | Vertalingen toevoegen/updaten |

### Voorbeelden
```bash
feat: Add contact person analysis to research
fix: Resolve race condition in interview submission
docs: Update API documentation for follow-up endpoints
refactor: [TD-009] Extract common router patterns
chore: Update dependencies to latest versions
i18n: Add v2 pricing translations for all languages
```

---

## 📅 Periodieke Reviews

### Wekelijks (Vrijdag)
- [ ] Review open tasks
- [ ] Update DEV_MASTER_PLAN progress
- [ ] Check deployment status

### Maandelijks (Eerste week)
- [ ] Update PRODUCT_OWNER_ANALYSIS.md
- [ ] Review RISK_REGISTER.md
- [ ] Review TECH_DEBT_REGISTER.md
- [ ] Plan volgende maand

### Kwartaal (Begin Q)
- [ ] Update COMPETITOR_ANALYSIS
- [ ] Review product strategy
- [ ] Update roadmap
- [ ] Retrospective

---

## 🔢 Nummering Systeem

### SPECs & TASKs

| Type | Laatste Nummer | Volgende |
|------|----------------|----------|
| SPEC | SPEC-040 ✅ | **SPEC-041** |
| TASK | TASK-045 ✅ | **TASK-046** |

### Tech Debt & Risks

| Type | Laatste Nummer | Volgende |
|------|----------------|----------|
| TD | TD-022 | **TD-023** |
| RISK | RISK-012 | **RISK-013** |

### Templates Gebruiken

**Nieuwe SPEC maken:**
```bash
1. Kopieer: specs/_TEMPLATE-SPEC.md
2. Hernoem: specs/SPEC-021-[Feature].md
3. Vul in en update PRODUCT_DOCS_INDEX.md
```

**Nieuwe TASK maken:**
```bash
1. Kopieer: tasks/_TEMPLATE-TASK.md
2. Hernoem: tasks/TASK-022-[Feature].md
3. Vul in en update PRODUCT_DOCS_INDEX.md
```

---

## 📁 Folder Structuur (Multi-Repo)

```
C:\Cursor\
│
├── 📱 dealmotion-web/              ← GitHub: styler1one/dealmotion-web
│   ├── frontend/                   ← Next.js (Vercel)
│   │   ├── app/
│   │   ├── components/
│   │   └── messages/
│   ├── backend/                    ← FastAPI (Railway)
│   │   ├── app/routers/
│   │   ├── app/services/
│   │   └── database/
│   └── README.md
│
├── 📲 dealmotion-mobile/           ← GitHub: styler1one/dealmotion-mobile
│   ├── lib/
│   │   ├── core/
│   │   ├── features/
│   │   └── shared/
│   ├── android/
│   ├── ios/
│   └── README.md
│
└── 📚 dealmotion-docs/             ← GitHub: styler1one/dealmotion-docs (PRIVATE)
    ├── specs/
    │   └── SPEC-XXX-[Feature].md   ← Feature specificaties
    ├── tasks/
    │   └── TASK-XXX-[Feature].md   ← Implementation tasks
    ├── DEV_MASTER_PLAN.md          ← Roadmap
    ├── CHANGELOG.md                ← Releases
    ├── TECH_DEBT_REGISTER.md       ← Tech debt
    ├── RISK_REGISTER.md            ← Risico's
    ├── PRODUCT_OWNER_ANALYSIS.md   ← Health check
    ├── PRODUCT_DOCS_INDEX.md       ← Document index
    └── WAYS_OF_WORKING.md          ← Dit document
```

### Cursor Workspaces

Open elk project in een **apart Cursor window** voor gefocuste AI context:

| Workspace | Doel | Open met |
|-----------|------|----------|
| `dealmotion-web` | Frontend + Backend development | `cursor C:\Cursor\dealmotion-web` |
| `dealmotion-mobile` | Flutter mobile app | `cursor C:\Cursor\dealmotion-mobile` |
| `dealmotion-docs` | Documentatie & specs | `cursor C:\Cursor\dealmotion-docs` |

---

## ✅ Checklists

### Voor Start Development
- [ ] SPEC bestaat en is approved
- [ ] TASK document aangemaakt
- [ ] DEV_MASTER_PLAN updated met nieuwe phase
- [ ] Dependencies geïdentificeerd

### Na Development
- [ ] Code gecommit met juiste message
- [ ] Deployed naar staging
- [ ] Getest op staging
- [ ] Deployed naar production
- [ ] CHANGELOG.md updated
- [ ] TASK marked as completed
- [ ] DEV_MASTER_PLAN phase marked ✅

### Maandelijkse Health Check
- [ ] PRODUCT_OWNER_ANALYSIS.md reviewed
- [ ] RISK_REGISTER.md reviewed
- [ ] TECH_DEBT_REGISTER.md reviewed
- [ ] Open bugs gecheckt
- [ ] Roadmap nog actueel?

---

## 🎯 Definition of Done

Een feature is "Done" wanneer:

- [ ] **Code**
  - [ ] Feature geïmplementeerd volgens SPEC
  - [ ] Geen linting errors
  - [ ] Geen console errors
  
- [ ] **Testing**
  - [ ] Handmatig getest
  - [ ] Edge cases gecheckt
  
- [ ] **Deployment**
  - [ ] Deployed naar production
  - [ ] Geen errors in logs
  
- [ ] **Documentation**
  - [ ] CHANGELOG updated
  - [ ] TASK marked complete
  - [ ] DEV_MASTER_PLAN updated

---

## 📞 Escalatie

### Wanneer Escaleren?
- Blocked > 2 uur
- Security issue ontdekt
- Data loss risico
- Production down

### Hoe Escaleren?
1. Document het probleem
2. Zoek eerst zelf naar oplossing
3. Als niet gevonden: vraag hulp
4. Log in RISK_REGISTER indien nieuw risico

---

## 🔚 Einde Sessie Checklist

Aan het einde van elke chat sessie:

- [ ] Update "Huidige Status" tabel met huidige fase/focus
- [ ] Update "Recent Afgerond" met wat er gedaan is
- [ ] Update "Volgende Stappen" met wat er nog moet
- [ ] Update "Bekende Aandachtspunten" indien nodig
- [ ] Update versienummer en datum

```
Vraag aan AI: "Update WOW met de huidige status voor handover"
```

---

**Dit document is de "single source of truth" voor hoe we werken. Bij twijfel: raadpleeg dit document!**

