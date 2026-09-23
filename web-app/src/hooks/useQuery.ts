import { useCallback, useEffect, useRef, useState } from "react";
import { ApiClientError, apiFetch } from "../lib/api";

export interface UseQueryOptions {
  enabled?: boolean;
  // Delay in milliseconds before showing skeleton to prevent visual flicker on fast (<300ms) responses
  skeletonDelayMs?: number;
}

export interface UseQueryResult<T> {
  data: T | null;
  loading: boolean;
  showSkeleton: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

export function useQuery<T>(
  path: string,
  options: UseQueryOptions = {}
): UseQueryResult<T> {
  const { enabled = true, skeletonDelayMs = 300 } = options;

  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState<boolean>(enabled);
  const [showSkeleton, setShowSkeleton] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);
  const timerRef = useRef<number | null>(null);

  const fetchData = useCallback(async (): Promise<void> => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    const controller = new AbortController();
    abortControllerRef.current = controller;

    setLoading(true);
    setError(null);

    // Apply the 300ms Rule: only show skeleton if request takes longer than threshold
    if (timerRef.current) {
      window.clearTimeout(timerRef.current);
    }
    timerRef.current = window.setTimeout(() => {
      setShowSkeleton(true);
    }, skeletonDelayMs);

    try {
      const result = await apiFetch<T>(path, {
        signal: controller.signal,
      });
      setData(result);
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === "AbortError") {
        return;
      }
      const message =
        err instanceof ApiClientError
          ? err.message
          : err instanceof Error
            ? err.message
            : "Une erreur inattendue est survenue";
      setError(message);
    } finally {
      if (timerRef.current) {
        window.clearTimeout(timerRef.current);
        timerRef.current = null;
      }
      setLoading(false);
      setShowSkeleton(false);
    }
  }, [path, skeletonDelayMs]);

  useEffect(() => {
    if (enabled) {
      void fetchData();
    }

    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      if (timerRef.current) {
        window.clearTimeout(timerRef.current);
      }
    };
  }, [enabled, fetchData]);

  return {
    data,
    loading,
    showSkeleton,
    error,
    refetch: fetchData,
  };
}

