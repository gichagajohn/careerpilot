import "./globals.css";

export const metadata = {
  title: "CareerPilot AI",
  description: "Personal AI career & scholarship agent",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
