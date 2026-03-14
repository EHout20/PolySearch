import { NextResponse } from 'next/server';
import { NextRequest } from 'next/server';

export async function GET(req: NextRequest) {
  try {
    const { searchParams } = req.nextUrl;
    const tokenId = searchParams.get('market');
    const interval = searchParams.get('interval') || 'max';
    const fidelity = searchParams.get('fidelity') || '1440';

    if (!tokenId) return NextResponse.json({ error: 'Missing market token ID' }, { status: 400 });

    const url = `https://clob.polymarket.com/prices-history?market=${tokenId}&interval=${interval}&fidelity=${fidelity}`;
    const resp = await fetch(url, {
      headers: { 'User-Agent': 'PolyLens/Next', Accept: 'application/json' },
      next: { revalidate: 300 }, // 5 min cache
    });

    if (!resp.ok) return NextResponse.json({ history: [] });

    const data = await resp.json();
    return NextResponse.json(data, { headers: { 'Access-Control-Allow-Origin': '*' } });
  } catch (error: any) {
    console.error('Price history proxy error:', error);
    return NextResponse.json({ history: [] });
  }
}
