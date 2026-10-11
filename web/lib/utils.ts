import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
    return twMerge(clsx(inputs));
}

/**
 * Normalize an EPIC number input by the user.
 * - Uppercase all letters.
 * - Strip all non-alphanumeric characters (spaces, hyphens, special chars).
 * Safe with null, undefined, or empty values.
 */
export function normalizeEpic(input: string | null | undefined): string {
    if (!input) return '';
    return String(input).toUpperCase().replace(/[^A-Z0-9]/g, '');
}

/**
 * Validate that a normalized EPIC number matches the expected format:
 * exactly 3 uppercase letters followed by 7 digits (10 chars total).
 */
export function isValidEpic(epic: string | null | undefined): boolean {
    if (!epic) return false;
    return /^[A-Z0-9]{10}$/.test(String(epic));
}

/**
 * Format an EPIC number for display (add a space after the 3-letter prefix
 * for readability in the UI — e.g., 'TYA 0633792').
 * The stored value in the database is always the unformatted version.
 * 100% null-safe: returns '—' if null or empty.
 */
export function formatEpicForDisplay(epic: string | null | undefined): string {
    if (!epic) return '—';
    const str = String(epic).trim();
    if (!str) return '—';
    if (str.length === 10) {
        return `${str.slice(0, 3)} ${str.slice(3)}`;
    }
    return str;
}

/**
 * Get initials from a name for the photo placeholder.
 * Example: 'RAVI KUMAR' -> 'RK'
 * 100% null-safe.
 */
export function getInitials(name: string | null | undefined): string {
    if (!name) return '?';
    const parts = String(name).trim().split(/\s+/).filter(Boolean);
    if (parts.length === 0) return '?';
    if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}
