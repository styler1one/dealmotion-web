import { 
    Loader2, 
    FileText, 
    Calendar, 
    CheckCircle, 
    Search, 
    Mic,
    Upload,
    AlertCircle,
    AlertTriangle,
    Trash2,
    RefreshCw,
    Clock,
    ArrowLeft,
    ArrowRight,
    ArrowUp,
    ArrowDown,
    ArrowUpDown,
    Download,
    Copy,
    Book,
    User,
    UserPlus,
    UserMinus,
    UserX,
    Pin,
    Mail,
    Building2,
    Home,
    Zap,
    PanelLeftClose,
    PanelLeftOpen,
    ChevronDown,
    ChevronUp,
    ChevronRight,
    ChevronLeft,
    LogOut,
    Settings,
    Bell,
    Menu,
    X,
    Plus,
    Target,
    TrendingUp,
    TrendingDown,
    Users,
    Briefcase,
    BarChart3,
    MessageSquare,
    Sparkles,
    Shield,
    Globe,
    Play,
    Check,
    Eye,
    Edit,
    Circle,
    Info,
    Sun,
    Moon,
    HelpCircle,
    Inbox,
    FolderOpen,
    Maximize2,
    Minimize2,
    Link2,
    Lightbulb,
    Activity,
    CreditCard,
    Heart,
    History,
    ExternalLink,
    DollarSign,
    FileWarning,
    Server,
    Database,
    XCircle,
    MoreHorizontal,
    Package,
    Lock,
    Radar,
    SearchX,
} from 'lucide-react'

// Custom Google Icon (official colors)
const GoogleIcon = ({ className }: { className?: string }) => (
    <svg viewBox="0 0 24 24" className={className}>
        <path
            fill="#4285F4"
            d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
        />
        <path
            fill="#34A853"
            d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
        />
        <path
            fill="#FBBC05"
            d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
        />
        <path
            fill="#EA4335"
            d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
        />
    </svg>
)

// Custom Microsoft Icon (official colors)
const MicrosoftIcon = ({ className }: { className?: string }) => (
    <svg viewBox="0 0 21 21" className={className}>
        <rect x="1" y="1" width="9" height="9" fill="#f25022" />
        <rect x="11" y="1" width="9" height="9" fill="#7fba00" />
        <rect x="1" y="11" width="9" height="9" fill="#00a4ef" />
        <rect x="11" y="11" width="9" height="9" fill="#ffb900" />
    </svg>
)

// Custom Fireflies Icon (purple gradient)
const FirefliesIcon = ({ className }: { className?: string }) => (
    <svg viewBox="0 0 24 24" className={className}>
        <defs>
            <linearGradient id="fireflies-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#8B5CF6" />
                <stop offset="100%" stopColor="#6366F1" />
            </linearGradient>
        </defs>
        <circle cx="12" cy="12" r="10" fill="url(#fireflies-gradient)" />
        <path d="M8 12c0-2.2 1.8-4 4-4s4 1.8 4 4-1.8 4-4 4" stroke="white" strokeWidth="1.5" fill="none" strokeLinecap="round" />
        <circle cx="12" cy="8" r="1.5" fill="white" />
        <circle cx="16" cy="12" r="1" fill="white" opacity="0.7" />
        <circle cx="8" cy="12" r="1" fill="white" opacity="0.7" />
    </svg>
)

// Custom Zoom Icon (blue)
const ZoomIcon = ({ className }: { className?: string }) => (
    <svg viewBox="0 0 24 24" className={className}>
        <rect x="2" y="5" width="20" height="14" rx="3" fill="#2D8CFF" />
        <path d="M7 9.5h5v5H7z" fill="white" />
        <path d="M14 10l4-2v8l-4-2v-4z" fill="white" />
    </svg>
)

// Custom Teams Icon (purple)
const TeamsIcon = ({ className }: { className?: string }) => (
    <svg viewBox="0 0 24 24" className={className}>
        <rect x="2" y="4" width="20" height="16" rx="2" fill="#5059C9" />
        <circle cx="16" cy="8" r="2.5" fill="white" />
        <path d="M12 14h8v3c0 1-1 2-2 2h-4c-1 0-2-1-2-2v-3z" fill="white" />
        <circle cx="8" cy="10" r="3" fill="#7B83EB" />
        <path d="M4 15h8v4c0 .5-.5 1-1 1H5c-.5 0-1-.5-1-1v-4z" fill="#7B83EB" />
    </svg>
)

// Custom Slack Icon
const SlackIcon = ({ className }: { className?: string }) => (
    <svg viewBox="0 0 24 24" className={className}>
        <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zM6.313 15.165a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313z" fill="#E01E5A"/>
        <path d="M8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zM8.834 6.313a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312z" fill="#36C5F0"/>
        <path d="M18.956 8.834a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.522V8.834zM17.688 8.834a2.528 2.528 0 0 1-2.523 2.521 2.527 2.527 0 0 1-2.52-2.521V2.522A2.527 2.527 0 0 1 15.165 0a2.528 2.528 0 0 1 2.523 2.522v6.312z" fill="#2EB67D"/>
        <path d="M15.165 18.956a2.528 2.528 0 0 1 2.523 2.522A2.528 2.528 0 0 1 15.165 24a2.527 2.527 0 0 1-2.52-2.522v-2.522h2.52zM15.165 17.688a2.527 2.527 0 0 1-2.52-2.523 2.526 2.526 0 0 1 2.52-2.52h6.313A2.527 2.527 0 0 1 24 15.165a2.528 2.528 0 0 1-2.522 2.523h-6.313z" fill="#ECB22E"/>
    </svg>
)

// Custom Salesforce Icon
const SalesforceIcon = ({ className }: { className?: string }) => (
    <svg viewBox="0 0 24 24" className={className}>
        <path d="M10.006 5.415a4.195 4.195 0 0 1 3.045-1.306c1.56 0 2.954.9 3.69 2.205.63-.3 1.35-.45 2.1-.45 2.85 0 5.159 2.34 5.159 5.22s-2.31 5.22-5.16 5.22c-.45 0-.9-.06-1.35-.15-.585 1.29-1.875 2.175-3.39 2.175a3.7 3.7 0 0 1-1.875-.51 4.313 4.313 0 0 1-4.005 2.715c-1.89 0-3.51-1.17-4.185-2.835a3.93 3.93 0 0 1-.99.12c-2.37 0-4.29-1.935-4.29-4.32 0-1.56.81-2.925 2.04-3.69a4.087 4.087 0 0 1-.3-1.545c0-2.37 1.875-4.29 4.2-4.29 1.2 0 2.295.51 3.075 1.32z" fill="#00A1E0"/>
    </svg>
)

// Custom HubSpot Icon
const HubSpotIcon = ({ className }: { className?: string }) => (
    <svg viewBox="0 0 24 24" className={className}>
        <path d="M17.66 13.34c-.98 0-1.77.79-1.77 1.77s.79 1.77 1.77 1.77 1.77-.79 1.77-1.77-.79-1.77-1.77-1.77zm-3.3-2.51V8.37c.57-.29.97-.87.97-1.54 0-.95-.77-1.72-1.72-1.72s-1.72.77-1.72 1.72c0 .67.39 1.25.97 1.54v2.46c-1.11.2-2.1.7-2.88 1.43l-4.22-3.29a1.77 1.77 0 0 0-.5-1.23 1.77 1.77 0 0 0-2.5 0 1.77 1.77 0 0 0 0 2.5c.34.34.78.52 1.23.52.15 0 .3-.02.44-.06l4.37 3.4c-.24.51-.38 1.07-.38 1.67 0 2.14 1.74 3.88 3.88 3.88s3.88-1.74 3.88-3.88c0-.6-.14-1.16-.38-1.67l2.29-2.29c.37.16.77.25 1.19.25 1.64 0 2.97-1.33 2.97-2.97s-1.33-2.97-2.97-2.97-2.97 1.33-2.97 2.97c0 .42.09.82.25 1.19l-2.2 2.2z" fill="#FF7A59"/>
    </svg>
)

export const Icons = {
    spinner: Loader2,
    fileText: FileText,
    calendar: Calendar,
    checkCircle: CheckCircle,
    search: Search,
    mic: Mic,
    upload: Upload,
    alertCircle: AlertCircle,
    trash: Trash2,
    refresh: RefreshCw,
    clock: Clock,
    arrowLeft: ArrowLeft,
    arrowRight: ArrowRight,
    arrowUp: ArrowUp,
    arrowDown: ArrowDown,
    arrowUpDown: ArrowUpDown,
    download: Download,
    copy: Copy,
    book: Book,
    user: User,
    userPlus: UserPlus,
    userMinus: UserMinus,
    userX: UserX,
    pin: Pin,
    mail: Mail,
    building: Building2,
    home: Home,
    zap: Zap,
    panelLeftClose: PanelLeftClose,
    panelLeftOpen: PanelLeftOpen,
    chevronDown: ChevronDown,
    chevronUp: ChevronUp,
    chevronRight: ChevronRight,
    logOut: LogOut,
    settings: Settings,
    bell: Bell,
    menu: Menu,
    x: X,
    plus: Plus,
    target: Target,
    trendingUp: TrendingUp,
    trendingDown: TrendingDown,
    users: Users,
    briefcase: Briefcase,
    barChart: BarChart3,
    message: MessageSquare,
    sparkles: Sparkles,
    shield: Shield,
    globe: Globe,
    play: Play,
    check: Check,
    eye: Eye,
    edit: Edit,
    circle: Circle,
    info: Info,
    sun: Sun,
    moon: Moon,
    helpCircle: HelpCircle,
    alertTriangle: AlertTriangle,
    inbox: Inbox,
    folderOpen: FolderOpen,
    maximize: Maximize2,
    minimize: Minimize2,
    link: Link2,
    lightbulb: Lightbulb,
    google: GoogleIcon,
    microsoft: MicrosoftIcon,
    fireflies: FirefliesIcon,
    zoom: ZoomIcon,
    teams: TeamsIcon,
    slack: SlackIcon,
    salesforce: SalesforceIcon,
    hubspot: HubSpotIcon,
    // Admin panel icons
    activity: Activity,
    creditCard: CreditCard,
    heart: Heart,
    history: History,
    externalLink: ExternalLink,
    chevronLeft: ChevronLeft,
    dollarSign: DollarSign,
    fileWarning: FileWarning,
    server: Server,
    database: Database,
    xCircle: XCircle,
    moreHorizontal: MoreHorizontal,
    package: Package,
    lock: Lock,
    radar: Radar,
    searchX: SearchX,
}
