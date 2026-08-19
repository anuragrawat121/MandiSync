/** Simple civic mark — not the national emblem. */
export default function GovMark({ className = "" }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 40 40"
      width="40"
      height="40"
      aria-hidden="true"
    >
      <rect width="40" height="40" rx="2" fill="#0c2744" />
      <path
        d="M8 28 V16 L20 9 L32 16 V28"
        fill="none"
        stroke="#f4ead4"
        strokeWidth="1.6"
        strokeLinejoin="miter"
      />
      <path d="M14 28 V21 H26 V28" fill="none" stroke="#f4ead4" strokeWidth="1.6" />
      <path d="M8 28 H32" stroke="#e07a12" strokeWidth="2" />
    </svg>
  );
}
