import Link from "next/link";
import { StatusIndicator } from "@/components/StatusIndicator";

export function SiteHeader() {
  return (
    <header className="site-header">
      <div className="site-header__inner">
        <Link className="wordmark" href="/">
          ProductIQ
        </Link>
        <p className="site-descriptor">AI-powered fashion discovery</p>
        <input className="nav-toggle" id="primary-nav-toggle" type="checkbox" />
        <label className="nav-toggle-label" htmlFor="primary-nav-toggle">
          Menu
        </label>
        <nav aria-label="Primary">
          <Link href="/search">Search</Link>
          <StatusIndicator />
        </nav>
      </div>
    </header>
  );
}
