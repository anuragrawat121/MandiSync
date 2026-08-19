import Link from "next/link";
import GovMark from "@/components/GovMark";

type Props = {
  children: React.ReactNode;
  current: "home" | "admin";
};

export default function SiteShell({ children, current }: Props) {
  return (
    <div className="gov-root">
      <a href="#main-content" className="gov-skip">
        Skip to main content
      </a>

      <div className="gov-tricolor" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>

      <header className="gov-masthead">
        <div className="gov-masthead-inner">
          <Link href="/" className="gov-brand">
            <GovMark className="gov-brand-mark" />
            <span>
              <span className="gov-brand-name">MandiSync</span>
              <span className="gov-brand-sub">
                Crop price &amp; logistics advisory
              </span>
            </span>
          </Link>

          <nav className="gov-nav" aria-label="Primary">
            <Link
              href="/"
              className={current === "home" ? "is-active" : undefined}
              aria-current={current === "home" ? "page" : undefined}
            >
              Corridors
            </Link>
            <Link
              href="/admin"
              className={current === "admin" ? "is-active" : undefined}
              aria-current={current === "admin" ? "page" : undefined}
            >
              Operations
            </Link>
          </nav>
        </div>
      </header>

      {children}

      <footer className="gov-footer">
        <div className="gov-footer-inner">
          <p>
            MandiSync is an independent advisory tool. It is not an official
            website of the Government of India, Agmarknet, or e-NAM.
          </p>
          <p>
            Wholesale prices are read from the public Agmarknet API on{" "}
            <a href="https://www.data.gov.in" target="_blank" rel="noopener noreferrer">
              data.gov.in
            </a>
            . Net profit is an estimate after transit, mandi fees, and spoilage
            — not a guaranteed payout. Confirm rates at the APMC yard before
            moving stock.
          </p>
          <p className="gov-footer-links">
            <a href="https://agmarknet.gov.in" target="_blank" rel="noopener noreferrer">
              Agmarknet
            </a>
            <span aria-hidden="true">·</span>
            <a
              href="https://enam.gov.in/web/apmc-contact-details"
              target="_blank"
              rel="noopener noreferrer"
            >
              e-NAM mandi directory
            </a>
            <span aria-hidden="true">·</span>
            <a href="tel:18002700224">e-NAM helpline 1800 270 0224</a>
          </p>
        </div>
      </footer>
    </div>
  );
}
