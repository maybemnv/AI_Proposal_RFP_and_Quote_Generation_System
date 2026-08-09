import type {Metadata} from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Arc / Studio",
  description: "Evidence-grounded proposal operations workspace",
};

export default function RootLayout({children}: Readonly<{children: React.ReactNode}>) {
  return <html lang="en"><body>{children}</body></html>;
}
