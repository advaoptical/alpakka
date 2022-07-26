package com.adva.alpakka;

import java.io.FileWriter;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;

import javax.annotation.Nonnull;

import com.google.common.collect.HashBasedTable;
import com.google.common.collect.Table;

import com.github.jknack.handlebars.Handlebars;
import com.github.jknack.handlebars.helper.StringHelpers;
import com.github.jknack.handlebars.io.ClassPathTemplateLoader;

import one.util.streamex.StreamEx;
import org.apache.commons.io.file.PathUtils;
import org.opendaylight.yangtools.plugin.generator.api.FileGenerator;
import org.opendaylight.yangtools.plugin.generator.api.FileGeneratorException;
import org.opendaylight.yangtools.plugin.generator.api.GeneratedFile;
import org.opendaylight.yangtools.plugin.generator.api.GeneratedFilePath;
import org.opendaylight.yangtools.plugin.generator.api.GeneratedFileType;
import org.opendaylight.yangtools.plugin.generator.api.ModuleResourceResolver;

import org.opendaylight.yangtools.yang.data.api.schema.DataContainerNode;
import org.opendaylight.yangtools.yang.model.api.*;
import org.opendaylight.yangtools.yang.model.api.Module;


public class PythonFileGenerator implements FileGenerator {

    @Nonnull
    private static final Handlebars HANDLEBARS = new Handlebars().with(new ClassPathTemplateLoader("/templates"))
            .registerHelpers(StringHelpers.class)
            .prettyPrint(true);

    @Nonnull
    private final Path pythonPackageDir;

    private PythonFileGenerator(@Nonnull final Path pythonPackageDir) {
        this.pythonPackageDir = pythonPackageDir;
    }

    @Nonnull
    public static PythonFileGenerator usingPythonPackageDir(@Nonnull final Path pythonPackageDir) {
        return new PythonFileGenerator(pythonPackageDir);
    }

    @Nonnull @Override
    public Table<GeneratedFileType, GeneratedFilePath, GeneratedFile> generateFiles(
            @Nonnull final EffectiveModelContext yangContext,
            @Nonnull final Set<Module> yangModules,
            @Nonnull final ModuleResourceResolver ignoredModuleResourcePathResolver)

            throws FileGeneratorException {

        for (@Nonnull final var yangModule : yangModules) {
            for (@Nonnull final var dataSchemaNode : yangModule.getChildNodes()) {
                if (dataSchemaNode instanceof ContainerSchemaNode containerSchemaNode) {
                    this.generatePychonClassPackage(this.pythonPackageDir, containerSchemaNode);
                }
            }
        }

        return HashBasedTable.create();
    }

    @Nonnull
    protected <C extends DataNodeContainer & DataSchemaNode>
    void generatePychonClassPackage(@Nonnull final Path parentPackageDir, @Nonnull final C yangContainer)
            throws FileGeneratorException {

        @Nonnull final var yangQName = yangContainer.getQName();
        @Nonnull final var yangContainerName = new YangName(yangQName.getLocalName());

        @Nonnull final var containerMembersContext = new HashSet<Map<String, Object>>();
        @Nonnull final var listMembersContext = new HashSet<Map<String, Object>>();


        @Nonnull final var packageDir = parentPackageDir.resolve(yangContainerName.toPythonName());
        try {
            Files.createDirectories(packageDir);

        } catch (IOException ex) {
            throw new FileGeneratorException(String.format("Failed creating directory %s", packageDir.toAbsolutePath()));
        }

        @Nonnull final var pythonFile = packageDir.resolve("__init__.py").toFile();

        for (@Nonnull final var dataSchemaNode : yangContainer.getChildNodes()) {
            if (dataSchemaNode instanceof ContainerSchemaNode containerMemberSchemaNode) {
                @Nonnull final var containerMemberName = new YangName(containerMemberSchemaNode.getQName().getLocalName());

                containerMembersContext.add(Map.of(
                        "yangName", containerMemberName,
                        "pythonName", containerMemberName.toPythonName(),
                        "className", containerMemberName.toPythonClassName()));

                this.generatePychonClassPackage(packageDir, containerMemberSchemaNode);

            } else if (dataSchemaNode instanceof ListSchemaNode listMemberSchemaNode) {
                @Nonnull final var listMemberName = new YangName(listMemberSchemaNode.getQName().getLocalName());

                listMembersContext.add(Map.of(
                        "yangName", listMemberName,
                        "pythonName", listMemberName.toPythonName(),
                        "className", listMemberName.toPythonClassName()));

                this.generatePychonClassPackage(packageDir, listMemberSchemaNode);
            }
        }

        try {
            @Nonnull final var pythonFileWriter = new FileWriter(pythonFile);
            HANDLEBARS.compile("class.py").apply(Map.of(
                    "yangName", yangContainerName,
                    "pythonName", yangContainerName.toPythonName(),
                    "className", yangContainerName.toPythonClassName(),

                    "containerMembers", containerMembersContext,
                    "listMembers", listMembersContext

            ), pythonFileWriter);;

            pythonFileWriter.close();

        } catch (final IOException e) {
            throw new FileGeneratorException(String.format("Failed creating %s from template class.py.hbs",
                    pythonFile.getAbsolutePath()

            ), e);
        }
    }
}
