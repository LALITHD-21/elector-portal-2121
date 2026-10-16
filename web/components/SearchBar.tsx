'use client';

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { normalizeEpic, isValidEpic } from '@/lib/utils';
import { prefetchElectorByEpic } from '@/lib/electorService';
import { Search, AlertCircle, Loader2, X, CheckCircle2, Sparkles } from 'lucide-react';

interface SearchBarProps {
  initialValue?: string;
  autoFocus?: boolean;
  onSearch?: (epic: string) => void;
  onClear?: () => void;
  isLoading?: boolean;
  placeholder?: string;
  size?: 'large' | 'compact';
  showCharCounter?: boolean;
}

export default function SearchBar({
  initialValue = '',
  autoFocus = true,
  onSearch,
  onClear,
  isLoading: externalLoading = false,
  placeholder = 'Enter 10-digit EPIC (e.g. TYA0633792)',
  size = 'large',
  showCharCounter = true,
}: SearchBarProps) {
  const router = useRouter();
  const [query, setQuery] = useState(initialValue);
  const [error, setError] = useState<string | null>(null);
  const [internalLoading, setInternalLoading] = useState(false);
  const [isFocused, setIsFocused] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const lastSearchedRef = useRef<string>('');

  const isLoading = externalLoading || internalLoading;

  useEffect(() => {
    if (initialValue !== query) {
      setQuery(normalizeEpic(initialValue));
    }
  }, [initialValue]);

  const executeSearch = useCallback((rawInput: string) => {
    setError(null);
    const normalized = normalizeEpic(rawInput);

    if (!normalized) {
      setError('Please enter an EPIC number.');
      return;
    }

    if (!isValidEpic(normalized)) {
      setError('Invalid EPIC format. Expected voter ID format (e.g. TYA0633792 or WWS579886).');
      return;
    }

    lastSearchedRef.current = normalized;

    if (onSearch) {
      onSearch(normalized);
    } else {
      setInternalLoading(true);
      router.push(`/profile/${encodeURIComponent(normalized)}`);
    }
  }, [onSearch, router]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const raw = e.target.value;
    const normalized = normalizeEpic(raw);
    const trimmed = normalized.slice(0, 14);
    setQuery(trimmed);

    if (error) setError(null);

    // Prefetch and auto-search when valid EPIC reached (typically 9-11 chars)
    if (trimmed.length >= 8 && isValidEpic(trimmed)) {
      prefetchElectorByEpic(trimmed);
      if (trimmed !== lastSearchedRef.current) {
        executeSearch(trimmed);
      }
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Escape') handleClear();
  };

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    executeSearch(query);
  };

  const handleClear = () => {
    setQuery('');
    setError(null);
    lastSearchedRef.current = '';
    if (onClear) onClear();
    inputRef.current?.focus();
  };

  const isValid = isValidEpic(query);
  const isComplete = isValid;
  const isCompact = size === 'compact';

  return (
    <div className={`w-full ${isCompact ? 'max-w-md' : 'max-w-xl'} mx-auto`}>
      <form onSubmit={handleSubmit} className="relative space-y-2" noValidate>
        {/* Glow halo when input is focused */}
        <div
          className={`absolute -inset-1 rounded-2xl bg-gradient-to-r ${
            isValid
              ? 'from-emerald-500/30 via-teal-500/20 to-emerald-500/30'
              : 'from-indigo-500/30 via-violet-500/20 to-purple-500/30'
          } blur-md transition-all duration-300 ${
            isFocused ? 'opacity-100 scale-[1.01]' : 'opacity-0 scale-100'
          }`}
        />

        <div className="relative flex items-center bg-white rounded-2xl border transition-all duration-200 shadow-sm hover:shadow-md">
          {/* Search Icon */}
          <div className="absolute inset-y-0 left-0 pl-3.5 sm:pl-4 flex items-center pointer-events-none text-slate-400">
            <Search className={isCompact ? 'w-4 h-4' : 'w-5 h-5 text-indigo-600'} />
          </div>

          {/* Main Search Input */}
          <input
            ref={inputRef}
            id="epic-search-input"
            type="text"
            value={query}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
            autoFocus={autoFocus}
            disabled={isLoading}
            maxLength={10}
            aria-label="EPIC Number search"
            placeholder={placeholder}
            className={`w-full epic-mono tracking-widest bg-transparent font-bold text-slate-900 placeholder:font-sans placeholder:tracking-normal placeholder:font-medium placeholder:text-slate-400 focus:outline-none transition ${
              isCompact
                ? 'pl-9 pr-24 py-2.5 text-xs sm:text-sm rounded-xl'
                : 'pl-11 sm:pl-12 pr-28 sm:pr-32 py-3.5 sm:py-4 text-sm sm:text-base md:text-lg rounded-2xl'
            } ${
              isValid
                ? 'border-emerald-500/80 focus:border-emerald-600 ring-2 ring-emerald-500/20'
                : 'border-slate-200 focus:border-indigo-600 ring-2 ring-indigo-500/10'
            } disabled:opacity-60 disabled:cursor-not-allowed`}
          />

          {/* Right Action Elements */}
          <div className="absolute inset-y-0 right-0 pr-2 flex items-center gap-1.5">
            {/* Real-time Validity Badge */}
            {showCharCounter && query.length > 0 && (
              <span
                className={`hidden sm:inline-flex items-center gap-1 text-[11px] font-mono font-bold px-2.5 py-1 rounded-lg transition-all ${
                  isValid
                    ? 'bg-emerald-50 text-emerald-700 border border-emerald-200/80 shadow-xs'
                    : isComplete
                    ? 'bg-rose-50 text-rose-600 border border-rose-200/80'
                    : 'bg-slate-100 text-slate-600'
                }`}
              >
                {isValid ? (
                  <>
                    <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                    <span>Ready</span>
                  </>
                ) : (
                  <span>{query.length}/10</span>
                )}
              </span>
            )}

            {/* Clear Button */}
            {query && !isLoading && (
              <button
                type="button"
                id="clear-search-button"
                onClick={handleClear}
                aria-label="Clear search input"
                className="p-1.5 text-slate-400 hover:text-slate-600 rounded-full hover:bg-slate-100 transition active:scale-90"
              >
                <X className="w-4 h-4" />
              </button>
            )}

            {/* Search Submit Button */}
            <button
              type="submit"
              id="submit-search-button"
              disabled={isLoading || !query}
              className={`inline-flex items-center justify-center font-bold rounded-xl shadow-md transition-all duration-200 active:scale-95 ${
                isCompact
                  ? 'px-3 py-1.5 text-xs'
                  : 'px-4 sm:px-5 py-2 sm:py-2.5 text-xs sm:text-sm'
              } ${
                isValid
                  ? 'bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 text-white shadow-emerald-500/20'
                  : 'bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-700 hover:to-violet-700 text-white shadow-indigo-500/20'
              } disabled:opacity-50 disabled:cursor-not-allowed`}
            >
              {isLoading ? (
                <Loader2 className={`${isCompact ? 'w-3.5 h-3.5' : 'w-4 h-4'} animate-spin`} />
              ) : (
                <div className="flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>Search</span>
                </div>
              )}
            </button>
          </div>
        </div>

        {/* Error Alert Box */}
        {error && (
          <div
            role="alert"
            className="flex items-center gap-2.5 px-3.5 py-2.5 text-xs md:text-sm text-rose-700 bg-rose-50/90 border border-rose-200/80 rounded-xl animate-fadeIn shadow-sm"
          >
            <AlertCircle className="w-4 h-4 flex-shrink-0 text-rose-500" />
            <span className="font-semibold">{error}</span>
          </div>
        )}
      </form>
    </div>
  );
}
