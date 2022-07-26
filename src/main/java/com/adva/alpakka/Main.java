package com.adva.alpakka;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Paths;
import java.util.Optional;
import java.util.regex.Pattern;

import javax.annotation.Nonnull;
import javax.annotation.Nullable;

import one.util.streamex.StreamEx;
import org.apache.commons.io.FileUtils;
import org.apache.commons.io.FilenameUtils;

import org.opendaylight.yangtools.plugin.generator.api.FileGeneratorException;
import org.opendaylight.yangtools.yang.common.QName;
import org.opendaylight.yangtools.yang.common.Revision;
import org.opendaylight.yangtools.yang.common.XMLNamespace;
import org.opendaylight.yangtools.yang.model.api.Module;

import org.opendaylight.mdsal.binding.runtime.spi.BindingRuntimeHelpers;

import org.opendaylight.yang.gen.v1.alpakka.norev.AlpakkaYangModuleInfo;


public class Main {

    @Nonnull
    private static final Pattern YANG_NAMESPACE_REGEX = Pattern.compile("^\\s*namespace\\s+\"?([^\"]+)\"?\\s*;\\s*$",
            Pattern.MULTILINE);

    @Nonnull
    public static void main(@Nonnull final String[] args) throws FileGeneratorException {

        @Nonnull final var yangDir = Paths.get(args[0]).toAbsolutePath();
        @Nullable final var yangFiles = yangDir.toFile().listFiles((ignoredDir, name) -> name.endsWith(".yang"));

        @Nonnull final var yangModuleInfos = StreamEx.of(yangFiles).map(yangFile -> {
            @Nonnull final String yangText;
            try {
                yangText = FileUtils.readFileToString(yangFile, StandardCharsets.UTF_8);

            } catch (final IOException e) {
                throw new RuntimeException(String.format("Failed reading %s", yangFile.getAbsolutePath()), e);
            }

            @Nonnull final var yangNameAndRevision = FilenameUtils.getBaseName(yangFile.getName()).split("@");
            @Nonnull final var yangName = yangNameAndRevision[0];
            @Nullable final var yangRevision = (yangNameAndRevision.length == 2) ? Revision.of(yangNameAndRevision[1]) : null;

            @Nonnull final var yangNamespaceRegexMatcher = YANG_NAMESPACE_REGEX.matcher(yangText);
            if (!yangNamespaceRegexMatcher.find()) {
                throw new RuntimeException(String.format("Failed to find namespace in %s", yangFile.getAbsolutePath()));
            }

            @Nonnull final var yangNamespace = XMLNamespace.of(yangNamespaceRegexMatcher.group(1));
            @Nonnull final var yangQName = QName.create(yangNamespace, Optional.ofNullable(yangRevision), yangName);

            return new AlpakkaYangModuleInfo(yangQName, yangText);

        }).toImmutableSet();

        @Nonnull final var yangContext = BindingRuntimeHelpers.createEffectiveModel(yangModuleInfos);
        @Nonnull final var yangModules = StreamEx.of(yangContext.getModules()).map(Module.class::cast).toImmutableSet();

        @Nonnull final var fileGenerator = PythonFileGenerator.usingPythonPackageDir(Paths.get(args[1]).toAbsolutePath());
        fileGenerator.generateFiles(yangContext, yangModules, (ignoredModule, ignoredRepresentation) -> Optional.empty());
    }
}
