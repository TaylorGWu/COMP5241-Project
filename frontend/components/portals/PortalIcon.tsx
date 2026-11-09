const paths = {
  book: "M4 4h6a3 3 0 0 1 3 3v13a4 4 0 0 0-4-2H4V4Zm16 0h-4a3 3 0 0 0-3 3v13a4 4 0 0 1 4-2h3V4Z",
  arrow: "M4 12h15m-6-6 6 6-6 6",
  overview: "M3 3h7v7H3V3Zm11 0h7v7h-7V3ZM3 14h7v7H3v-7Zm11 0h7v7h-7v-7Z",
  applications: "M8 5H5v16h14V5h-3M8 3h8v4H8V3Zm0 9h8m-8 4h5",
  users:
    "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2m20 0v-2a4 4 0 0 0-3-3.87M13 3.13a4 4 0 0 1 0 7.75M13 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0Z",
  activity: "M22 12a10 10 0 1 1-3-7.14M22 3v6h-6m-4-3v6l4 2",
  chevron: "m6 9 6 6 6-6",
  check: "m5 12 4 4L19 7",
} as const;

export function PortalIcon({ name }: { name: keyof typeof paths }) {
  return (
    <svg
      className="portal-icon"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d={paths[name]} />
    </svg>
  );
}
