"use client";

import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type AnchorHTMLAttributes,
  type ComponentType,
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode,
} from "react";

import { BellIcon, ChevronIcon, CloseIcon, MenuIcon, UserIcon } from "./icons";

/**
 * Application shell (A-10-T05): top navigation, org switcher slot, practice navigation, breadcrumbs,
 * user menu, notification bell and job tray slot. Responsive from 360 px to 1440 px: below 1024 px
 * the navigation moves into a drawer opened by a 44 px menu button.
 *
 * The component holds no user-visible text of its own — every label arrives through props, so the
 * app passes i18n messages (en-CA / fr-CA) and the shell never hard-codes a string.
 */

export interface ShellNavItem {
  id: string;
  label: string;
  href: string;
  /** Marks the item for the current page (`aria-current="page"`). */
  current?: boolean;
}

export interface ShellNavGroup {
  /** Accessible name of the navigation landmark and the drawer section heading. */
  label: string;
  items: ShellNavItem[];
}

export interface ShellCrumb {
  label: string;
  /** Omit on the last crumb (the current page). */
  href?: string;
}

export interface ShellUserMenuItem {
  id: string;
  label: string;
  href?: string;
  onSelect?: () => void;
}

export interface ShellLabels {
  skipToContent: string;
  primaryNav: string;
  breadcrumbs: string;
  openMenu: string;
  closeMenu: string;
  /** Accessible name of the mobile navigation drawer. */
  mobileNav: string;
}

export type ShellLinkComponent = ComponentType<
  AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }
>;

export interface AppShellProps {
  labels: ShellLabels;
  /** Brand mark link (accessible name, e.g. "Numo9 — Home"). */
  brand: { label: string; href: string };
  nav: ShellNavItem[];
  /** Accountant's practice links (Directory, Dashboard, …); shown in the sub-bar and the drawer. */
  practiceNav?: ShellNavGroup;
  breadcrumbs?: ShellCrumb[];
  /** Slot: organisation switcher (A-01-T14). */
  orgSwitcher?: ReactNode;
  /** Slot: global search / command palette trigger (A-09). Hidden below 768 px. */
  search?: ReactNode;
  /** Slot: background job tray (A-08). Hidden below 768 px. */
  jobTray?: ReactNode;
  /** Notification bell (A-07 opens the notification centre). `label` should include the count. */
  notifications: { label: string; count?: number; onOpen?: () => void };
  /** User menu: `label` is the button's accessible name, e.g. "Account menu: Dana Lee". */
  user: { label: string; name?: string; initials?: string; items: ShellUserMenuItem[] };
  /** Right-hand end of the breadcrumb bar (e.g. the trial countdown chip). */
  status?: ReactNode;
  /** Link component (Next.js `Link`); defaults to `<a>`. */
  linkComponent?: ShellLinkComponent;
  children: ReactNode;
}

const DefaultLink: ShellLinkComponent = (props) => <a {...props} />;

const ICON_BUTTON =
  "inline-flex size-touch-target shrink-0 items-center justify-center rounded-md " +
  "text-fg-inverse hover:bg-surface-inverse-hover";

export function AppShell({
  labels,
  brand,
  nav,
  practiceNav,
  breadcrumbs = [],
  orgSwitcher,
  search,
  jobTray,
  notifications,
  user,
  status,
  linkComponent: Link = DefaultLink,
  children,
}: AppShellProps) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const drawerId = useId();
  const menuButton = useRef<HTMLButtonElement>(null);
  const drawer = useRef<HTMLDivElement>(null);

  const closeDrawer = useCallback((returnFocus = true) => {
    setDrawerOpen(false);
    if (returnFocus) menuButton.current?.focus();
  }, []);

  useEffect(() => {
    if (!drawerOpen) return;
    drawer.current?.querySelector<HTMLElement>("a, button")?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeDrawer();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [drawerOpen, closeDrawer]);

  return (
    <div className="flex min-h-screen flex-col bg-surface text-fg">
      <a
        href="#main-content"
        className="sr-only z-50 rounded-md bg-surface-accent px-4 py-2 font-semibold text-fg-on-accent focus:not-sr-only focus:absolute focus:start-2 focus:top-2"
      >
        {labels.skipToContent}
      </a>

      <header
        data-shell="top-nav"
        className="sticky top-0 z-40 bg-surface-inverse text-fg-inverse [&_:focus-visible]:outline-border-focus-inverse"
      >
        <div className="flex h-top-nav items-center gap-2 px-2 md:px-4">
          <button
            ref={menuButton}
            type="button"
            className={`${ICON_BUTTON} lg:hidden`}
            aria-expanded={drawerOpen}
            aria-controls={drawerId}
            aria-label={drawerOpen ? labels.closeMenu : labels.openMenu}
            onClick={() => (drawerOpen ? closeDrawer() : setDrawerOpen(true))}
          >
            {drawerOpen ? <CloseIcon /> : <MenuIcon />}
          </button>

          <Link
            href={brand.href}
            aria-label={brand.label}
            className="inline-flex size-touch-target shrink-0 items-center justify-center rounded-md"
          >
            {/* The mark is drawn as generated content: a logo, not a text label, so the link's
                accessible name ("Numo9 home") is the only name (WCAG 2.5.3, A-10-T19). */}
            <span
              aria-hidden="true"
              data-mark="N9"
              className="inline-flex size-8 items-center justify-center rounded-md bg-surface-accent text-sm font-extrabold text-fg-on-accent before:content-[attr(data-mark)]"
            />
          </Link>

          {orgSwitcher ? (
            <div
              data-shell="org-switcher"
              className="flex min-w-0 flex-1 lg:max-w-60 lg:flex-initial"
            >
              {orgSwitcher}
            </div>
          ) : null}

          <nav aria-label={labels.primaryNav} className="hidden min-w-0 lg:ms-4 lg:block">
            <ul className="flex items-center gap-1">
              {nav.map((item) => (
                <li key={item.id}>
                  <Link
                    href={item.href}
                    aria-current={item.current ? "page" : undefined}
                    className={
                      "relative flex h-top-nav items-center px-3 text-sm font-medium whitespace-nowrap " +
                      (item.current
                        ? "font-bold text-fg-inverse-accent after:absolute after:inset-x-3 after:bottom-0 after:h-1 after:bg-surface-accent"
                        : "text-fg-inverse-muted hover:text-fg-inverse")
                    }
                  >
                    {item.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>

          <div className="ms-auto flex shrink-0 items-center gap-1">
            {search ? (
              <div data-shell="search" className="hidden md:block">
                {search}
              </div>
            ) : null}
            {jobTray ? (
              <div data-shell="job-tray" className="hidden md:block">
                {jobTray}
              </div>
            ) : null}
            <NotificationBell {...notifications} />
            <UserMenu {...user} />
          </div>
        </div>
      </header>

      {drawerOpen ? (
        <div className="fixed inset-x-0 top-top-nav bottom-0 z-30 lg:hidden">
          <button
            type="button"
            tabIndex={-1}
            aria-hidden="true"
            className="absolute inset-0 size-full cursor-default bg-surface-inverse/40"
            onClick={() => closeDrawer()}
          />
          <div
            id={drawerId}
            ref={drawer}
            role="dialog"
            aria-modal="true"
            aria-label={labels.mobileNav}
            className="absolute inset-y-0 start-0 w-75 max-w-[85vw] overflow-y-auto bg-surface p-2 shadow-elevation-3"
          >
            <DrawerList
              label={labels.primaryNav}
              items={nav}
              Link={Link}
              onNavigate={() => closeDrawer(false)}
            />
            {practiceNav ? (
              <>
                <hr className="my-2 border-border" />
                <DrawerList
                  label={practiceNav.label}
                  heading
                  items={practiceNav.items}
                  Link={Link}
                  onNavigate={() => closeDrawer(false)}
                />
              </>
            ) : null}
          </div>
        </div>
      ) : (
        <div id={drawerId} hidden />
      )}

      <div data-shell="sub-bar" className="border-b border-border bg-surface">
        <div className="flex min-h-10 flex-wrap items-center gap-x-4 gap-y-1 px-4 py-2 md:px-6">
          {breadcrumbs.length ? (
            <Breadcrumbs label={labels.breadcrumbs} crumbs={breadcrumbs} Link={Link} />
          ) : null}
          {practiceNav ? (
            <nav aria-label={practiceNav.label} className="ms-auto hidden lg:block">
              <ul className="flex items-center gap-4 text-sm">
                {practiceNav.items.map((item) => (
                  <li key={item.id}>
                    <Link
                      href={item.href}
                      aria-current={item.current ? "page" : undefined}
                      className={
                        item.current ? "font-semibold text-fg" : "text-fg-muted hover:text-fg"
                      }
                    >
                      {item.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </nav>
          ) : null}
          {status ? <div className={practiceNav ? "" : "ms-auto"}>{status}</div> : null}
        </div>
      </div>

      <main id="main-content" tabIndex={-1} className="flex-1 px-4 py-6 outline-none md:px-6">
        {children}
      </main>
    </div>
  );
}

function DrawerList({
  label,
  items,
  heading = false,
  Link,
  onNavigate,
}: {
  label: string;
  items: ShellNavItem[];
  heading?: boolean;
  Link: ShellLinkComponent;
  onNavigate: () => void;
}) {
  return (
    <nav aria-label={label}>
      {heading ? (
        <p className="px-4 pt-3 pb-1 text-xs font-bold tracking-wide text-fg-muted uppercase">
          {label}
        </p>
      ) : null}
      <ul>
        {items.map((item) => (
          <li key={item.id}>
            <Link
              href={item.href}
              aria-current={item.current ? "page" : undefined}
              onClick={onNavigate}
              className={
                "flex min-h-touch-target items-center rounded-md px-4 text-base " +
                (item.current
                  ? "border-s-4 border-border-accent bg-surface-accent-subtle font-semibold"
                  : "text-fg hover:bg-surface-muted")
              }
            >
              {item.label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}

/** Breadcrumbs; below 768 px only the last two crumbs show, after an ellipsis. */
export function Breadcrumbs({
  label,
  crumbs,
  Link = DefaultLink,
}: {
  label: string;
  crumbs: ShellCrumb[];
  Link?: ShellLinkComponent;
}) {
  const collapsed = crumbs.length > 2;
  return (
    <nav aria-label={label} className="min-w-0">
      <ol className="flex min-w-0 items-center gap-1 text-xs font-medium text-fg-muted">
        {collapsed ? (
          <li aria-hidden="true" className="md:hidden">
            …
          </li>
        ) : null}
        {crumbs.map((crumb, index) => {
          const last = index === crumbs.length - 1;
          const hiddenOnPhone = collapsed && index < crumbs.length - 2;
          return (
            <li
              key={`${index}-${crumb.label}`}
              className={`min-w-0 items-center gap-1 ${hiddenOnPhone ? "hidden md:flex" : "flex"}`}
            >
              {index > 0 || collapsed ? (
                <span
                  className={`text-fg-subtle ${index === 0 ? "md:hidden" : ""}`}
                  aria-hidden="true"
                >
                  <ChevronIcon />
                </span>
              ) : null}
              {last || !crumb.href ? (
                <span aria-current={last ? "page" : undefined} className="truncate text-fg">
                  {crumb.label}
                </span>
              ) : (
                <Link href={crumb.href} className="truncate hover:text-fg hover:underline">
                  {crumb.label}
                </Link>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

function NotificationBell({ label, count = 0, onOpen }: AppShellProps["notifications"]) {
  return (
    <button
      type="button"
      data-shell="notifications"
      className={`${ICON_BUTTON} relative`}
      aria-label={label}
      onClick={onOpen}
    >
      <BellIcon />
      {count > 0 ? (
        <span
          aria-hidden="true"
          className="absolute end-1.5 top-1.5 min-w-4 rounded-full bg-surface-accent px-1 text-center text-xs leading-4 font-bold text-fg-on-accent"
        >
          {count > 99 ? "99+" : count}
        </span>
      ) : null}
    </button>
  );
}

function UserMenu({ label, name, initials, items }: AppShellProps["user"]) {
  const [open, setOpen] = useState(false);
  const menuId = useId();
  const button = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLUListElement>(null);
  const root = useRef<HTMLDivElement>(null);

  const menuItems = () => [
    ...(menu.current?.querySelectorAll<HTMLElement>("[role=menuitem]") ?? []),
  ];

  const close = useCallback((returnFocus: boolean) => {
    setOpen(false);
    if (returnFocus) button.current?.focus();
  }, []);

  useEffect(() => {
    if (!open) return;
    menuItems()[0]?.focus();
    const onPointer = (event: MouseEvent) => {
      if (!root.current?.contains(event.target as Node)) close(false);
    };
    document.addEventListener("mousedown", onPointer);
    return () => document.removeEventListener("mousedown", onPointer);
  }, [open, close]);

  const onMenuKey = (event: ReactKeyboardEvent<HTMLUListElement>) => {
    const list = menuItems();
    const index = list.indexOf(document.activeElement as HTMLElement);
    const focusAt = (i: number) => list[(i + list.length) % list.length]?.focus();
    switch (event.key) {
      case "ArrowDown":
        event.preventDefault();
        focusAt(index + 1);
        break;
      case "ArrowUp":
        event.preventDefault();
        focusAt(index - 1);
        break;
      case "Home":
        event.preventDefault();
        focusAt(0);
        break;
      case "End":
        event.preventDefault();
        focusAt(list.length - 1);
        break;
      case "Escape":
        event.preventDefault();
        close(true);
        break;
      case "Tab":
        close(false);
        break;
    }
  };

  return (
    <div ref={root} data-shell="user-menu" className="relative">
      <button
        ref={button}
        type="button"
        className={`${ICON_BUTTON} rounded-full`}
        aria-label={label}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={menuId}
        onClick={() => setOpen((value) => !value)}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown" && !open) {
            event.preventDefault();
            setOpen(true);
          }
        }}
      >
        <span className="inline-flex size-8 items-center justify-center rounded-full bg-surface-accent text-xs font-bold text-fg-on-accent">
          {/* Initials are a decorative avatar (generated content); the name is `label`. */}
          {initials ? (
            <span
              aria-hidden="true"
              data-initials={initials}
              className="before:content-[attr(data-initials)]"
            />
          ) : (
            <UserIcon />
          )}
        </span>
      </button>
      <ul
        ref={menu}
        id={menuId}
        role="menu"
        aria-label={label}
        hidden={!open}
        onKeyDown={onMenuKey}
        className="absolute end-0 top-full z-50 mt-1 min-w-56 rounded-lg border border-border bg-surface py-1 text-fg shadow-elevation-2 [&_:focus-visible]:outline-border-focus"
      >
        {name ? (
          <li role="none" className="border-b border-border px-4 py-2 text-sm font-semibold">
            {name}
          </li>
        ) : null}
        {items.map((item) => (
          <li key={item.id} role="none">
            {item.href ? (
              <a
                role="menuitem"
                tabIndex={-1}
                href={item.href}
                className="flex min-h-touch-target items-center px-4 text-sm hover:bg-surface-muted focus:bg-surface-muted"
                onClick={() => {
                  item.onSelect?.();
                  close(false);
                }}
              >
                {item.label}
              </a>
            ) : (
              <button
                role="menuitem"
                tabIndex={-1}
                type="button"
                className="flex min-h-touch-target w-full items-center px-4 text-start text-sm hover:bg-surface-muted focus:bg-surface-muted"
                onClick={() => {
                  item.onSelect?.();
                  close(true);
                }}
              >
                {item.label}
              </button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
