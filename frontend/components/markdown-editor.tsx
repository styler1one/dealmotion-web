'use client'

import { useEffect, useCallback } from 'react'
import { LexicalComposer } from '@lexical/react/LexicalComposer'
import { RichTextPlugin } from '@lexical/react/LexicalRichTextPlugin'
import { ContentEditable } from '@lexical/react/LexicalContentEditable'
import { HistoryPlugin } from '@lexical/react/LexicalHistoryPlugin'
import { OnChangePlugin } from '@lexical/react/LexicalOnChangePlugin'
import { LexicalErrorBoundary } from '@lexical/react/LexicalErrorBoundary'
import { MarkdownShortcutPlugin } from '@lexical/react/LexicalMarkdownShortcutPlugin'
import { useLexicalComposerContext } from '@lexical/react/LexicalComposerContext'
import { HeadingNode, QuoteNode } from '@lexical/rich-text'
import { ListNode, ListItemNode } from '@lexical/list'
import { CodeNode, CodeHighlightNode } from '@lexical/code'
import { LinkNode, AutoLinkNode } from '@lexical/link'
import { ListPlugin } from '@lexical/react/LexicalListPlugin'
import { LinkPlugin } from '@lexical/react/LexicalLinkPlugin'
import { 
  $convertFromMarkdownString, 
  $convertToMarkdownString,
  TRANSFORMERS 
} from '@lexical/markdown'
import { $getRoot, EditorState } from 'lexical'
import { cn } from '@/lib/utils'

// Theme voor de editor
const editorTheme = {
  paragraph: 'mb-2 text-slate-700 dark:text-slate-300',
  heading: {
    h1: 'text-2xl font-bold mb-4 text-slate-900 dark:text-white',
    h2: 'text-xl font-bold mt-6 mb-3 pb-2 border-b border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white',
    h3: 'text-lg font-semibold mt-4 mb-2 text-slate-900 dark:text-white',
  },
  list: {
    ul: 'list-disc list-inside mb-4 space-y-1 ml-4',
    ol: 'list-decimal list-inside mb-4 space-y-1 ml-4',
    listitem: 'text-slate-700 dark:text-slate-300',
    nested: {
      listitem: 'ml-4',
    },
  },
  quote: 'border-l-4 border-slate-300 dark:border-slate-600 pl-4 italic text-slate-600 dark:text-slate-400 my-4',
  code: 'bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 rounded text-sm font-mono text-slate-800 dark:text-slate-200',
  codeHighlight: {
    atrule: 'text-purple-600',
    attr: 'text-blue-600',
    boolean: 'text-orange-600',
    builtin: 'text-cyan-600',
    cdata: 'text-slate-500',
    char: 'text-green-600',
    class: 'text-yellow-600',
    'class-name': 'text-yellow-600',
    comment: 'text-slate-500',
    constant: 'text-orange-600',
    deleted: 'text-red-600',
    doctype: 'text-slate-500',
    entity: 'text-orange-600',
    function: 'text-blue-600',
    important: 'text-orange-600',
    inserted: 'text-green-600',
    keyword: 'text-purple-600',
    namespace: 'text-slate-600',
    number: 'text-orange-600',
    operator: 'text-slate-600',
    prolog: 'text-slate-500',
    property: 'text-blue-600',
    punctuation: 'text-slate-600',
    regex: 'text-green-600',
    selector: 'text-green-600',
    string: 'text-green-600',
    symbol: 'text-orange-600',
    tag: 'text-red-600',
    url: 'text-cyan-600',
    variable: 'text-orange-600',
  },
  link: 'text-blue-600 dark:text-blue-400 underline hover:text-blue-800 dark:hover:text-blue-300',
  text: {
    bold: 'font-bold',
    italic: 'italic',
    strikethrough: 'line-through',
    underline: 'underline',
    code: 'bg-slate-100 dark:bg-slate-800 px-1 py-0.5 rounded text-sm font-mono',
  },
}

// Nodes die we ondersteunen
const editorNodes = [
  HeadingNode,
  QuoteNode,
  ListNode,
  ListItemNode,
  CodeNode,
  CodeHighlightNode,
  LinkNode,
  AutoLinkNode,
]

interface MarkdownEditorProps {
  value: string
  onChange: (markdown: string) => void
  placeholder?: string
  className?: string
  disabled?: boolean
}

// Plugin om initial markdown te laden
function InitialContentPlugin({ markdown }: { markdown: string }) {
  const [editor] = useLexicalComposerContext()

  useEffect(() => {
    editor.update(() => {
      $convertFromMarkdownString(markdown, TRANSFORMERS)
    })
  }, []) // Only run once on mount

  return null
}

// Plugin om changes te tracken en naar markdown te converteren
function MarkdownChangePlugin({ onChange }: { onChange: (markdown: string) => void }) {
  const handleChange = useCallback((editorState: EditorState) => {
    editorState.read(() => {
      const markdown = $convertToMarkdownString(TRANSFORMERS)
      onChange(markdown)
    })
  }, [onChange])

  return <OnChangePlugin onChange={handleChange} />
}

// Toolbar component
function Toolbar() {
  const [editor] = useLexicalComposerContext()

  const formatHeading = (level: 'h1' | 'h2' | 'h3') => {
    editor.update(() => {
      // Simple heading insert - user can also use markdown shortcuts
    })
  }

  return (
    <div className="flex items-center gap-1 p-2 border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50 rounded-t-lg">
      <span className="text-xs text-slate-500 dark:text-slate-400 px-2">
        Markdown shortcuts: **bold**, *italic*, # heading, - list, &gt; quote
      </span>
    </div>
  )
}

export function MarkdownEditor({ 
  value, 
  onChange, 
  placeholder = 'Start typing...', 
  className,
  disabled = false 
}: MarkdownEditorProps) {
  const initialConfig = {
    namespace: 'BriefEditor',
    theme: editorTheme,
    nodes: editorNodes,
    onError: (error: Error) => {
      console.error('Lexical error:', error)
    },
    editable: !disabled,
  }

  return (
    <div className={cn(
      'rounded-lg border border-slate-200 dark:border-slate-700 overflow-hidden',
      disabled && 'opacity-60 cursor-not-allowed',
      className
    )}>
      <LexicalComposer initialConfig={initialConfig}>
        <Toolbar />
        <div className="relative min-h-[500px] bg-white dark:bg-slate-900">
          <RichTextPlugin
            contentEditable={
              <ContentEditable 
                className="min-h-[500px] p-4 outline-none prose prose-slate dark:prose-invert max-w-none"
              />
            }
            placeholder={
              <div className="absolute top-4 left-4 text-slate-400 dark:text-slate-500 pointer-events-none">
                {placeholder}
              </div>
            }
            ErrorBoundary={LexicalErrorBoundary}
          />
          <HistoryPlugin />
          <ListPlugin />
          <LinkPlugin />
          <MarkdownShortcutPlugin transformers={TRANSFORMERS} />
          <InitialContentPlugin markdown={value} />
          <MarkdownChangePlugin onChange={onChange} />
        </div>
      </LexicalComposer>
    </div>
  )
}

