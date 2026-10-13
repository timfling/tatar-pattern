"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

type ShellContextValue = {
  screenEl: HTMLElement | null;
  setScreenEl: (el: HTMLElement | null) => void;
  setConstructorClick: (fn: (() => void) | null) => void;
  runConstructorClick: () => void;
  showBack: boolean;
  setShowBack: (show: boolean) => void;
  setBackHandler: (fn: (() => void) | null) => void;
  runBack: () => void;
};

const ShellContext = createContext<ShellContextValue | null>(null);

export function ShellProvider({ children }: { children: ReactNode }) {
  const [screenEl, setScreenEl] = useState<HTMLElement | null>(null);
  const [showBack, setShowBack] = useState(false);
  const constructorClick = useRef<(() => void) | null>(null);
  const backHandler = useRef<(() => void) | null>(null);

  const setConstructorClick = useCallback((fn: (() => void) | null) => {
    constructorClick.current = fn;
  }, []);

  const setBackHandler = useCallback((fn: (() => void) | null) => {
    backHandler.current = fn;
  }, []);

  const runConstructorClick = useCallback(() => {
    constructorClick.current?.();
  }, []);

  const runBack = useCallback(() => {
    backHandler.current?.();
  }, []);

  const value = useMemo(
    () => ({
      screenEl,
      setScreenEl,
      setConstructorClick,
      runConstructorClick,
      showBack,
      setShowBack,
      setBackHandler,
      runBack,
    }),
    [screenEl, setConstructorClick, runConstructorClick, showBack, setBackHandler, runBack],
  );

  return (
    <ShellContext.Provider value={value}>{children}</ShellContext.Provider>
  );
}

export function useShell(): ShellContextValue {
  const ctx = useContext(ShellContext);
  if (!ctx) {
    throw new Error("useShell: нет оболочки страницы");
  }
  return ctx;
}
