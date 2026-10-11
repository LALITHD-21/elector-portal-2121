import { NextRequest, NextResponse } from 'next/server';
import { dispatchPendingNotifications, getNotificationsList } from '@/lib/notifications';
import { requireRole, isAuthError, isInternalAdminAuthorized } from '@/lib/auth/roles';

export async function POST(request: NextRequest) {
  try {
    const isInternal = isInternalAdminAuthorized(request);
    const auth = requireRole(request, 'admin', 'supervisor');

    if (!isInternal && isAuthError(auth)) {
      return NextResponse.json({ error: auth.error }, { status: auth.status });
    }

    const result = await dispatchPendingNotifications();
    return NextResponse.json({
      success: true,
      message: `Dispatched ${result.sent} pending notifications.`,
      ...result,
    });
  } catch (error: any) {
    console.error('Notification dispatch error:', error);
    return NextResponse.json(
      { error: error.message || 'Notification dispatch failed' },
      { status: 500 }
    );
  }
}

export async function GET(request: NextRequest) {
  try {
    const isInternal = isInternalAdminAuthorized(request);
    const auth = requireRole(request, 'admin', 'supervisor');

    if (!isInternal && isAuthError(auth)) {
      return NextResponse.json({ error: auth.error }, { status: auth.status });
    }

    const list = await getNotificationsList();
    const queuedCount = list.filter((n) => n.status === 'queued').length;
    const sentCount = list.filter((n) => n.status === 'sent').length;

    return NextResponse.json({
      notifications: list.slice(-50).reverse(),
      stats: {
        total: list.length,
        queued: queuedCount,
        sent: sentCount,
      },
    });
  } catch (error: any) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
