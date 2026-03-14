import { NextResponse } from 'next/server';
import { NextRequest } from 'next/server';

type Params = { path: string[] };

export async function GET(req: NextRequest, { params }: { params: Promise<Params> }) {
  try {
    const { path } = await params;
    const pathStr = path.join('/');
    const search = req.nextUrl.search || '';
    const gammaUrl = `https://gamma-api.polymarket.com/${pathStr}${search}`;

    const resp = await fetch(gammaUrl, {
      method: 'GET',
      headers: {
        'User-Agent': 'Mozilla/5.0 (compatible; PolyLens/Next)',
        'Accept': 'application/json',
      },
      next: { revalidate: 30 },
    });

    if (!resp.ok) {
      return NextResponse.json({ error: `Gamma API error: ${resp.status}` }, { status: resp.status });
    }

    const data = await resp.json();
    return NextResponse.json(data, {
      headers: { 'Access-Control-Allow-Origin': '*' }
    });
  } catch (error: any) {
    console.error('Gamma Proxy Error:', error);
    return NextResponse.json({ error: error.message }, { status: 502 });
  }
}
