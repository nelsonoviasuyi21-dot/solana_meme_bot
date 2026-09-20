package com.ovi.tradingbeast;

import android.app.Activity;
import android.os.Bundle;
import android.graphics.*;
import android.view.*;
import android.content.*;

public class MainActivity extends Activity {

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        setContentView(new Dashboard(this));
    }

    static class Dashboard extends View {

        Paint p = new Paint(1);
        float d;

        int BG = Color.rgb(8,11,18);
        int CARD = Color.rgb(17,23,33);
        int TEXT = Color.WHITE;
        int MUTED = Color.rgb(145,157,174);
        int GREEN = Color.rgb(53,227,154);
        int RED = Color.rgb(255,88,100);
        int BLUE = Color.rgb(75,155,255);

        Dashboard(Context c) {
            super(c);
            d = getResources().getDisplayMetrics().density;
        }

        float dp(float x) {
            return x * d;
        }

        void txt(Canvas c,String s,float x,float y,float size,
                 int color,boolean bold) {
            p.setStyle(Paint.Style.FILL);
            p.setColor(color);
            p.setTextSize(dp(size));
            p.setTypeface(Typeface.create(
                "sans",
                bold ? Typeface.BOLD : Typeface.NORMAL));
            c.drawText(s,dp(x),dp(y),p);
        }

        void card(Canvas c,float l,float t,float r,float b) {
            p.setStyle(Paint.Style.FILL);
            p.setColor(CARD);
            c.drawRoundRect(
                dp(l),dp(t),dp(r),dp(b),
                dp(12),dp(12),p);
        }

        void value(Canvas c,String label,String val,
                   float x,float y,int color) {
            txt(c,label,x,y,10,MUTED,true);
            txt(c,val,x,y+22,16,color,true);
        }

        @Override
        protected void onDraw(Canvas c) {

            c.drawColor(BG);

            float w = getWidth()/d;
            float y = 32;

            txt(c,"OVI PLUS",18,y,12,GREEN,true);
            txt(c,"TRADING BEAST",18,y+29,25,TEXT,true);
            txt(c,"SOLANA MEME-COIN ENGINE",
                18,y+49,10,MUTED,true);

            p.setColor(GREEN);
            p.setStyle(Paint.Style.FILL);
            c.drawCircle(dp(w-32),dp(37),dp(6),p);

            txt(c,"RUNNING",w-92,42,11,GREEN,true);

            y = 105;

            card(c,14,y,w-14,y+72);

            txt(c,"BOT STATUS",28,y+25,10,MUTED,true);
            txt(c,"RUNNING",28,y+50,18,GREEN,true);

            txt(c,"MODE",w/2,y+25,10,MUTED,true);
            txt(c,"PAPER TRADING",
                w/2,y+50,15,BLUE,true);

            y += 92;

            txt(c,"CURRENT POSITION",18,y,13,TEXT,true);

            card(c,14,y+15,w-14,y+105);

            txt(c,"NONE",28,y+50,21,MUTED,true);

            txt(c,"Waiting for qualified token...",
                28,y+74,12,MUTED,false);

            y += 125;

            txt(c,"TRADING ENGINE",18,y,13,TEXT,true);

            card(c,14,y+15,w-14,y+145);

            float col = w/2;

            value(c,"WALLET BALANCE",
                "0.008470 SOL",28,y+44,TEXT);

            value(c,"TAKE PROFIT",
                "+17%",col,y+44,GREEN);

            value(c,"ENTRY PRICE",
                "—",28,y+92,MUTED);

            value(c,"CURRENT PRICE",
                "—",col,y+92,MUTED);

            value(c,"CURRENT P/L",
                "0.00%",28,y+140,MUTED);

            value(c,"TIME IN POSITION",
                "—",col,y+140,MUTED);

            y += 170;

            txt(c,"SCANNER",18,y,13,TEXT,true);

            card(c,14,y+15,w-14,y+90);

            p.setColor(GREEN);
            c.drawCircle(dp(30),dp(y+43),dp(5),p);

            txt(c,"SCANNING FOR QUALIFIED TOKENS",
                44,y+48,12,TEXT,true);

            txt(c,"Entry score >= 50  |  Buy ratio >= 65%",
                28,y+73,10,MUTED,false);

            y += 110;

            txt(c,"LATEST SIGNAL",18,y,13,TEXT,true);

            card(c,14,y+15,w-14,y+83);

            txt(c,"WAITING",28,y+45,15,MUTED,true);

            txt(c,"No qualified entry yet",
                28,y+66,11,MUTED,false);


            y += 105;

            txt(c,"PERFORMANCE",18,y,13,TEXT,true);

            card(c,14,y+15,w-14,y+130);

            value(c,"TRADES TAKEN","0",
                28,y+43,TEXT);

            value(c,"TAKE PROFITS","0",
                col,y+43,GREEN);

            value(c,"REJECTED","0",
                28,y+89,MUTED);

            value(c,"WIN RATE","0%",
                col,y+89,TEXT);

            y += 150;

            txt(c,"BOT HEALTH",18,y,13,TEXT,true);

            card(c,14,y+15,w-14,y+78);

            txt(c,"ENGINE",28,y+40,10,MUTED,true);
            txt(c,"ONLINE",28,y+59,13,GREEN,true);

            txt(c,"PAPER EXECUTOR",
                col,y+40,10,MUTED,true);

            txt(c,"READY",
                col,y+59,13,GREEN,true);

            y += 105;

            txt(c,"CONTROLS",18,y,13,TEXT,true);

            button(c,14,y+15,w/2-7,y+60,
                "START BOT",GREEN);

            button(c,w/2+7,y+15,w-14,y+60,
                "STOP BOT",RED);

            button(c,14,y+70,w/2-7,y+115,
                "RESTART",BLUE);

            button(c,w/2+7,y+70,w-14,y+115,
                "EMERGENCY STOP",RED);

            y += 145;

            txt(c,"LAST UPDATE",18,y,10,MUTED,true);

            txt(c,"Waiting for bot connection...",
                18,y+20,11,MUTED,false);
        }

        void button(Canvas c,float l,float t,float r,float b,
                    String title,int color) {

            p.setStyle(Paint.Style.FILL);
            p.setColor(Color.rgb(24,31,43));

            c.drawRoundRect(
                dp(l),dp(t),dp(r),dp(b),
                dp(10),dp(10),p);

            p.setStyle(Paint.Style.STROKE);
            p.setStrokeWidth(dp(1));
            p.setColor(color);

            c.drawRoundRect(
                dp(l),dp(t),dp(r),dp(b),
                dp(10),dp(10),p);

            p.setTextAlign(Paint.Align.CENTER);

            txt(c,title,(l+r)/2,(t+b)/2+4,
                11,color,true);

            p.setTextAlign(Paint.Align.LEFT);
        }
    }
}
