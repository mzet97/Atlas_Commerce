import type { Metadata } from "next";
import { cookies } from "next/headers";
import { currentUser, SESSION_COOKIE } from "@/lib/auth";
import "./globals.css";

export const metadata: Metadata = {
  title: "Atlas Storefront (M2 slice)",
  description: "Products projected from domain events. Availability is indicative.",
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const user = await currentUser((await cookies()).get(SESSION_COOKIE)?.value);
  return (
    <html lang="pt-BR">
      <body>
        <header className="site-header">
          <a href="/" className="brand">Atlas</a>
          <nav>
            <a href="/search">buscar</a>
            <a href="/recommendations">para você</a>
            {user ? (
              <>
                <span className="user">{user}</span>
                <a href="/logout">sair</a>
              </>
            ) : (
              <a href="/login">entrar</a>
            )}
          </nav>
        </header>
        {children}
      </body>
    </html>
  );
}
