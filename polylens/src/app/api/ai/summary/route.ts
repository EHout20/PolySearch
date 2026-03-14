import { NextResponse } from 'next/server';

export async function POST(req: Request) {
  try {
    const api_key = process.env.GOOGLE_API_KEY;
    if (!api_key) {
      return NextResponse.json({ error: 'GOOGLE_API_KEY not found in server environment' }, { status: 500 });
    }

    const postData = await req.json();
    const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-lite:generateContent?key=${api_key}`;

    const resp = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(postData),
    });

    const data = await resp.json();
    return NextResponse.json(data);
  } catch (error: any) {
    console.error('AI Proxy Error:', error);
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
