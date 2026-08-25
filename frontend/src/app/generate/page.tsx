"use client";

import Sidebar from "@/components/Sidebar";
import Navbar from "@/components/Navbar";
import Step0Overview from "./components/Step0Overview";
import Step1Upload from "./components/Step1Upload";
import Step2Settings from "./components/Step2Settings";
import Step3AIProcessing from "./components/Step3AIProcessing";
import Step4PreviewEdit from "./components/Step4PreviewEdit";
import Step5Export from "./components/Step5Export";
import { useGenerateWizard } from "./hooks/useGenerateWizard";

// Seluruh state & logic wizard (fetch upload/AI/save, dst) ada di useGenerateWizard() —
// file ini murni menyusun tampilan: header stepper 5-langkah + routing ke komponen Step yang
// sesuai currentStep. Sebelumnya semuanya (~1200 baris) ada langsung di 1 fungsi komponen ini.
export default function GenerateReportPage() {
  const w = useGenerateWizard();
  const { tx, currentStep } = w;

  const renderStepCircle = (stepNum: number) => {
    if (currentStep > stepNum) {
      return (
        <div className="w-8 h-8 rounded-full bg-petro-green text-white flex items-center justify-center font-bold text-xs shadow-sm border-2 border-petro-green">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
            className="w-4 h-4"
          >
            <path
              fillRule="evenodd"
              d="M16.704 4.153a.75.75 0 0 1 .143 1.052l-8 10.5a.75.75 0 0 1-1.127.075l-4.5-4.5a.75.75 0 0 1 1.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 0 1 1.05-.143Z"
              clipRule="evenodd"
            />
          </svg>
        </div>
      );
    } else if (currentStep === stepNum) {
      return (
        <div className="w-8 h-8 rounded-full bg-petro-green text-white flex items-center justify-center font-bold text-xs shadow-sm border-2 border-petro-green">
          {stepNum}
        </div>
      );
    } else {
      return (
        <div className="w-8 h-8 rounded-full bg-white text-stone-400 border border-stone-200 flex items-center justify-center font-bold text-xs shadow-sm">
          {stepNum}
        </div>
      );
    }
  };

  return (
    <div className="min-h-screen bg-petro-bg-warm flex">
      {/* Sidebar Navigation */}
      <Sidebar />

      {/* Main Content Area */}
      <div className="flex-1 pl-0 md:pl-64 flex flex-col min-h-screen">
        <Navbar />

        {/* Main Body */}
        <main className="flex-1 p-4 sm:p-6 md:p-8 max-w-6xl mx-auto w-full">
          {/* STEPPER LOGO & METRIC (Only show if step > 0) */}
          {currentStep > 0 && (
            <div className="w-full flex justify-center mb-10">
              <div className="w-full max-w-3xl relative animate-fadeIn">
                {/* ── BACKGROUND CONTINUOUS SEAMLESS TRACK ── */}
                {/* Garis background utuh membentang presisi dari pusat Step 1 ke Step 5 */}
                <div className="absolute top-4 left-4 right-4 h-0.5 bg-stone-200 -translate-y-1/2 z-0">
                  {/* Active Green Progress Line yang meluncur dinamis & smooth tanpa celah */}
                  <div
                    className="h-full bg-petro-green transition-all duration-500 ease-out"
                    style={{
                      width: `${Math.max(0, Math.min(100, ((currentStep - 1) / 4) * 100))}%`,
                    }}
                  />
                </div>

                {/* ── STEP CIRCLES AND LABELS ── */}
                <div className="relative z-10 flex justify-between items-start w-full">
                  {/* Step 1 */}
                  <div className="flex flex-col items-center">
                    <div className="relative z-10">{renderStepCircle(1)}</div>
                    <span className="text-[10px] font-bold text-stone-600 mt-2">
                      {tx("Upload Data", "Upload Data")}
                    </span>
                  </div>

                  {/* Step 2 */}
                  <div className="flex flex-col items-center">
                    <div className="relative z-10">{renderStepCircle(2)}</div>
                    <span className="text-[10px] font-bold text-stone-600 mt-2">
                      {tx("Report Settings", "Report Settings")}
                    </span>
                  </div>

                  {/* Step 3 */}
                  <div className="flex flex-col items-center">
                    <div className="relative z-10">{renderStepCircle(3)}</div>
                    <span className="text-[10px] font-bold text-stone-600 mt-2">
                      {tx("AI Processing", "AI Processing")}
                    </span>
                  </div>

                  {/* Step 4 */}
                  <div className="flex flex-col items-center">
                    <div className="relative z-10">{renderStepCircle(4)}</div>
                    <span className="text-[10px] font-bold text-stone-600 mt-2">
                      {tx("Preview & Edit", "Preview & Edit")}
                    </span>
                  </div>

                  {/* Step 5 */}
                  <div className="flex flex-col items-center">
                    <div className="relative z-10">{renderStepCircle(5)}</div>
                    <span className="text-[10px] font-bold text-stone-600 mt-2">
                      {tx("Export", "Export")}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {currentStep > 0 && <hr className="border-stone-200/60 mb-8" />}

          {/* errorMsg sebelumnya cuma dirender di dalam Step3AIProcessing (step 3) - validasi
              Step 2 (format export/section belum dipilih) yang men-set errorMsg SEBELUM pindah
              ke step 3 jadi tidak pernah terlihat sama sekali kalau cuma mengandalkan itu.
              Dirender di sini supaya terlihat di step mana pun errorMsg di-set. */}
          {w.errorMsg && currentStep !== 3 && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl text-xs font-semibold text-left mb-6">
              {w.errorMsg}
            </div>
          )}

          {/* STEP 0: OVERVIEW / HOW IT WORKS */}
          {currentStep === 0 && (
            <Step0Overview onStart={() => w.setCurrentStep(1)} tx={tx} />
          )}

          {/* STEP 1: UPLOAD DATA */}
          {currentStep === 1 && (
            <Step1Upload
              files={w.files}
              rawFiles={w.rawFiles}
              onFileDrop={w.handleFileDrop}
              onFileSelect={w.handleFileSelect}
              onFileRemove={w.handleRemoveFile}
              onNext={w.handleNextStep}
              onBack={w.handleBackStep}
              tx={tx}
            />
          )}

          {/* STEP 2: REPORT SETTINGS */}
          {currentStep === 2 && (
            <Step2Settings
              periodStart={w.periodStart}
              setPeriodStart={w.setPeriodStart}
              periodEnd={w.periodEnd}
              setPeriodEnd={w.setPeriodEnd}
              periodAutoDetected={w.periodAutoDetected}
              periodDetecting={w.periodDetecting}
              onPeriodManualEdit={() => w.setPeriodAutoDetected(false)}
              language={w.language}
              setLanguage={w.setLanguage}
              exportFormats={w.exportFormats}
              setExportFormats={w.setExportFormats}
              sections={w.sections}
              setSections={w.setSections}
              dynamicSections={w.dynamicSections}
              setDynamicSections={w.setDynamicSections}
              sectionsLoading={w.sectionsLoading}
              headerTitle={w.headerTitle}
              setHeaderTitle={w.setHeaderTitle}
              headerSubtitle={w.headerSubtitle}
              setHeaderSubtitle={w.setHeaderSubtitle}
              themeColor={w.themeColor}
              setThemeColor={w.setThemeColor}
              stylePreset={w.stylePreset}
              setStylePreset={w.setStylePreset}
              templateType={w.templateType}
              setTemplateType={w.setTemplateType}
              tone={w.tone}
              setTone={w.setTone}
              defaultLevel={w.defaultLevel}
              setDefaultLevel={w.setDefaultLevel}
              onNext={w.handleStartGeneration}
              onBack={w.handleBackStep}
              tx={tx}
            />
          )}

          {/* STEP 3: AI PROCESSING */}
          {currentStep === 3 && (
            <Step3AIProcessing
              aiStatus={w.aiStatus}
              processingStep={w.processingStep}
              processingStartedAt={w.processingStartedAt}
              estimatedSeconds={w.estimatedSeconds}
              tokensGenerated={w.tokensGenerated}
              expectedTotalTokens={w.expectedTotalTokens}
              reportDetails={w.reportDetails}
              errorMsg={w.errorMsg}
              canRetry={!!w.reportId}
              onBack={w.handleBackStep}
              onProceed={w.handleProceedToEditor}
              onRetry={w.handleRetryAnalysis}
              onCancel={w.handleCancelGeneration}
              tx={tx}
            />
          )}

          {/* STEP 4: PREVIEW & EDIT */}
          {currentStep === 4 && (
            <Step4PreviewEdit
              activePage={w.activePage}
              setActivePage={w.setActivePage}
              activeTab={w.activeTab}
              setActiveTab={w.setActiveTab}
              isSaving={w.isSaving}
              saveSuccess={w.saveSuccess}
              language={w.language}
              periodStart={w.periodStart}
              periodEnd={w.periodEnd}
              reportDetails={w.reportDetails}
              reportTitle={w.title}
              editedSummary={w.editedSummary}
              pages={w.pages}
              blocks={w.blocks}
              visualStyle={w.visualStyle}
              themeColor={w.resolvedThemeColor}
              blocksLoading={w.blocksLoading}
              blocksError={w.blocksError}
              getPageText={w.getPageText}
              getPageTitle={w.getPageTitle}
              handleTextChange={w.handleTextChange}
              handleSaveEdits={w.handleSaveEdits}
              onBack={w.handleBackStep}
              onNext={w.handleNextStep}
              onRenameTitle={w.handleRenameTitle}
              tx={tx}
            />
          )}

          {/* STEP 5: EXPORT */}
          {currentStep === 5 && (
            <Step5Export
              reportId={w.reportId}
              reportTitle={w.title}
              exportFormats={w.exportFormats}
              onReset={w.resetWizard}
              onBack={w.handleBackStep}
              tx={tx}
            />
          )}
        </main>
      </div>
    </div>
  );
}
