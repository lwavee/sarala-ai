import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Link from "next/link";
import { MessageSquare, FolderKanban, Settings, Home } from "lucide-react";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Sarla AI",
  description: "Aapki AI Dost with Voice Assistant",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body suppressHydrationWarning className={`${inter.className} flex h-screen overflow-hidden bg-black text-cyan-500 font-mono`}>
        {/* Sidebar */}
        <aside className="w-64 border-r border-cyan-500/30 flex flex-col justify-between hidden md:flex transition-all relative overflow-hidden jarvis-panel">
          <div className="absolute inset-0 bg-cyan-900/10 jarvis-scan"></div>
          <div className="p-6 relative z-10">
            <h1 className="text-3xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-blue-600 mb-8 uppercase tracking-widest animate-pulse">
              J.A.R.V.I.S
            </h1>
            <nav className="space-y-2">
              <Link href="/" className="flex items-center gap-3 px-4 py-3 rounded-none border-l-2 border-transparent hover:border-cyan-400 transition-colors text-cyan-600 hover:text-cyan-300 hover:bg-cyan-900/20 uppercase tracking-widest text-sm">
                <Home size={20} />
                <span>Core</span>
              </Link>
              <Link href="/chatbot" className="flex items-center gap-3 px-4 py-3 rounded-none border-l-2 border-cyan-400 bg-cyan-900/20 text-cyan-300 hover:bg-cyan-900/40 transition-colors uppercase tracking-widest text-sm shadow-[inset_0_0_10px_rgba(34,211,238,0.2)]">
                <MessageSquare size={20} />
                <span>Interface</span>
              </Link>
              <Link href="/project" className="flex items-center gap-3 px-4 py-3 rounded-none border-l-2 border-transparent hover:border-cyan-400 transition-colors text-cyan-600 hover:text-cyan-300 hover:bg-cyan-900/20 uppercase tracking-widest text-sm">
                <FolderKanban size={20} />
                <span>Databases</span>
              </Link>
            </nav>
          </div>
          <div className="p-6 border-t border-cyan-500/30 relative z-10">
            <button className="flex items-center gap-3 px-4 py-3 w-full rounded-none border-l-2 border-transparent hover:border-cyan-400 transition-colors text-cyan-600 hover:text-cyan-300 hover:bg-cyan-900/20 uppercase tracking-widest text-sm">
              <Settings size={20} />
              <span>Protocols</span>
            </button>
          </div>
        </aside>

        {/* Main Content */}
        <main className="flex-1 flex flex-col h-full relative overflow-hidden bg-black">
          {/* Subtle grid background */}
          <div className="absolute inset-0 bg-[linear-gradient(rgba(34,211,238,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(34,211,238,0.03)_1px,transparent_1px)] bg-[size:40px_40px] pointer-events-none"></div>
          {children}
        </main>
      </body>
    </html>
  );
}
