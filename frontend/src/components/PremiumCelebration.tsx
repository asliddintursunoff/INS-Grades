import React, { useEffect, useRef } from 'react';
import { Sparkles, Check, ArrowRight } from 'lucide-react';
import { useLanguage } from '../i18n';

interface PremiumCelebrationProps {
  isOpen: boolean;
  onClose: () => void;
}

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  size: number;
  color: string;
  rotation: number;
  rotationSpeed: number;
  opacity: number;
}

export const PremiumCelebration: React.FC<PremiumCelebrationProps> = ({ isOpen, onClose }) => {
  const { t } = useLanguage();
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    if (!isOpen) return;

    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;

    const colors = ['#f59e0b', '#fbbf24', '#10b981', '#3b82f6', '#ec4899', '#8b5cf6', '#eab308'];
    const particles: Particle[] = [];
    const count = 100;

    for (let i = 0; i < count; i++) {
      const angle = (Math.PI * 2 * i) / count + (Math.random() - 0.5);
      const speed = Math.random() * 8 + 4;
      particles.push({
        x: canvas.width / 2,
        y: canvas.height / 2 - 40,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed - 3,
        size: Math.random() * 8 + 4,
        color: colors[Math.floor(Math.random() * colors.length)],
        rotation: Math.random() * 360,
        rotationSpeed: (Math.random() - 0.5) * 10,
        opacity: 1,
      });
    }

    let animationFrameId: number;

    const render = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      particles.forEach((p) => {
        p.x += p.vx;
        p.y += p.vy;
        p.vy += 0.2; // Gravity
        p.vx *= 0.98; // Friction
        p.rotation += p.rotationSpeed;
        p.opacity -= 0.005; // Fade out slowly

        if (p.opacity > 0) {
          ctx.save();
          ctx.globalAlpha = Math.max(0, p.opacity);
          ctx.translate(p.x, p.y);
          ctx.rotate((p.rotation * Math.PI) / 180);
          ctx.fillStyle = p.color;
          ctx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size * 0.6);
          ctx.restore();
        }
      });

      if (particles.some((p) => p.opacity > 0)) {
        animationFrameId = requestAnimationFrame(render);
      }
    };

    render();

    return () => {
      cancelAnimationFrame(animationFrameId);
    };
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-300">
      {/* Confetti Canvas */}
      <canvas
        ref={canvasRef}
        className="pointer-events-none fixed inset-0 z-10 w-full h-full"
      />

      {/* Celebratory Modal Dialog */}
      <div className="relative z-20 bg-white rounded-3xl max-w-sm w-full p-6 text-center shadow-2xl border-2 border-amber-300/80 space-y-4 animate-in zoom-in-95 duration-300">
        {/* Glowing Badge & Star Animation */}
        <div className="relative mx-auto w-20 h-20 flex items-center justify-center">
          <div className="absolute inset-0 rounded-full bg-gradient-to-tr from-amber-400 via-yellow-300 to-amber-200 animate-ping opacity-30"></div>
          <div className="relative w-18 h-18 rounded-3xl bg-gradient-to-tr from-amber-400 via-amber-300 to-yellow-400 text-slate-950 flex items-center justify-center shadow-lg border-2 border-amber-200 transform hover:scale-105 transition-transform">
            <span className="text-3xl animate-bounce">⭐</span>
          </div>
        </div>

        {/* Celebration Title */}
        <div className="space-y-1">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-100 text-amber-900 text-xs font-black uppercase tracking-wider mb-1">
            <Sparkles className="w-3.5 h-3.5 text-amber-600 animate-spin" />
            <span>{t('celebration_badge')}</span>
          </div>
          <h2 className="text-xl font-black text-slate-900 tracking-tight leading-snug">
            {t('celebration_title')}
          </h2>
          <p className="text-xs text-slate-600 leading-relaxed font-medium">
            {t('celebration_desc')}
          </p>
        </div>

        {/* Unlocked Benefits Quick Checklist */}
        <div className="bg-gradient-to-br from-amber-50/60 to-yellow-50/30 border border-amber-200/70 rounded-2xl p-3.5 text-left space-y-2 text-xs text-slate-800">
          <div className="flex items-center gap-2 font-bold text-emerald-700">
            <Check className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>{t('celebration_item1')}</span>
          </div>
          <div className="flex items-center gap-2 font-bold text-emerald-700">
            <Check className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>{t('celebration_item2')}</span>
          </div>
          <div className="flex items-center gap-2 font-bold text-emerald-700">
            <Check className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>{t('celebration_item3')}</span>
          </div>
          <div className="flex items-center gap-2 font-bold text-emerald-700">
            <Check className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>{t('celebration_item4')}</span>
          </div>
        </div>

        {/* Primary Action Button */}
        <button
          onClick={onClose}
          className="w-full py-3 px-4 rounded-2xl bg-gradient-to-r from-amber-500 via-amber-400 to-yellow-400 hover:from-amber-600 hover:to-yellow-500 text-slate-950 font-black text-sm shadow-md flex items-center justify-center gap-2 transition-all active:scale-[0.98]"
        >
          <span>{t('celebration_btn')}</span>
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};
